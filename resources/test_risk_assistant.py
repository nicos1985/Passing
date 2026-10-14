import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.urls import reverse, set_urlconf
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from resources.models import AssetType, InformationAssets, RiskEvaluation, RiskInsight, Threat, Vulnerability
from resources.risk_assistant import run_daily
from supporthub.models import TelegramRecipient, TelegramEventDelivery


@override_settings(ROOT_URLCONF='passing.urls_tenant', RISK_ASSISTANT_AI_ENABLED=True)
class RiskAssistantTests(TenantTestCase):
    def setUp(self):
        set_urlconf('passing.urls_tenant')
        self.addCleanup(set_urlconf, None)
        user_model = get_user_model()
        self.admin = user_model.objects.create_user('riskadmin', 'admin@example.com', 'pass', client=self.tenant)
        self.admin.is_staff = True
        self.admin.save()
        self.other = user_model.objects.create_user('other', 'other@example.com', 'pass', client=self.tenant)
        asset = InformationAssets.objects.create(name='SECRET-asset.internal', owner=self.admin, asset_type=AssetType.PC_OR_NOTEBOOK)
        threat = Threat.objects.create(name='SECRET-threat')
        vulnerability = Vulnerability.objects.create(
            name='SECRET-vulnerability', type_vulnerability=1,
            description='SECRET falta de parches en server.example.com',
        )
        self.evaluation = RiskEvaluation.objects.create(
            evaluated_type=ContentType.objects.get_for_model(asset), evaluated_id=asset.pk,
            threat=threat, vulnerability=vulnerability, description='SECRET acceso sin MFA 10.0.0.1 admin@example.com',
            is_draft=True,
        )
        self.client = TenantClient(self.tenant)

    def test_external_payload_has_only_abstract_facts_and_deduplicates(self):
        class FakeClient:
            requests = []

            def create_message(self, system, message, **kwargs):
                self.requests.append((system, message))
                if 'open_count' in json.loads(message):
                    return json.dumps({'message': 'Empezaría por revisar la evaluación pendiente y dejar asentado el próximo paso.'})
                return json.dumps({'items': [{
                    'ref': 'R1', 'priority': 'high',
                    'tip': 'Revisá los permisos y la autenticación; después registrá la decisión en la evaluación.',
                }]})

        fake = FakeClient()
        with patch('supporthub.telegram_events.queue_risk_assistant_digest') as queue:
            run = run_daily(client=fake)
            self.assertEqual(run.created_count, 1)
            self.assertTrue(run.digest_ai_used)
            self.assertTrue(run.insights.get().tip_ai_used)
            self.assertIn('permisos', run.insights.get().tip)
            self.assertIn('Para avanzar hoy:', run.digest_text)
            self.assertIn('Buen día', run.digest_text)
            self.assertIn('Empezaría', run.digest_text)
            self.assertEqual(run_daily(client=fake).pk, run.pk)
            self.assertEqual(run_daily(client=fake, force=True).created_count, 1)
            self.assertEqual(queue.call_count, 2)
        self.assertEqual(RiskInsight.objects.count(), 1)
        next_run = run_daily(day=run.day + timedelta(days=1), client=fake)
        self.assertEqual(next_run.created_count, 0)
        self.assertEqual(RiskInsight.objects.count(), 1)
        self.assertEqual(len(fake.requests), 4)
        outbound = json.dumps(fake.requests)
        for secret in ('SECRET', '10.0.0.1', 'admin@example.com', 'server.example.com'):
            self.assertNotIn(secret, outbound)
        self.assertTrue(all('"id":' not in message for _, message in fake.requests))
        self.assertEqual(json.loads(fake.requests[0][1])['items'][0]['ref'], 'R1')
        self.assertEqual(json.loads(fake.requests[0][1])['items'][0]['vulnerability_family'], 'software')
        self.assertIn('authentication', json.loads(fake.requests[0][1])['items'][0]['themes'])
        self.assertIn('patching', json.loads(fake.requests[0][1])['items'][0]['themes'])
        self.assertEqual(json.loads(fake.requests[1][1])['open_count'], 1)

    def test_invalid_ai_digest_uses_local_text(self):
        class FakeClient:
            def create_message(self, system, message, **kwargs):
                if 'open_count' in json.loads(message):
                    return json.dumps({'message': 'Podés revisar el detalle en https://sitio.example.com'})
                return json.dumps({'items': [{
                    'ref': 'R1', 'priority': 'high',
                    'tip': 'Revisá los datos en https://sitio.example.com',
                }]})

        with patch('supporthub.telegram_events.queue_risk_assistant_digest'):
            run = run_daily(client=FakeClient())
        self.assertFalse(run.digest_ai_used)
        self.assertIn('Buen día', run.digest_text)
        self.assertNotIn('https://', run.digest_text)
        self.assertFalse(run.insights.get().tip_ai_used)
        self.assertNotIn('https://', run.insights.get().tip)

    def test_changed_description_replaces_case_without_inflating_daily_count(self):
        with patch('supporthub.telegram_events.queue_risk_assistant_digest'):
            run = run_daily(use_ai=False)
            self.evaluation.description = 'SECRET respaldo pendiente en 10.0.0.1'
            self.evaluation.save(update_fields=['description', 'updated'])
            run = run_daily(force=True, use_ai=False)
        self.assertEqual(run.created_count, 1)
        self.assertEqual(RiskInsight.objects.filter(status=RiskInsight.Status.OPEN).count(), 1)
        self.assertEqual(RiskInsight.objects.filter(status=RiskInsight.Status.SUPERSEDED).count(), 1)

    @override_settings(RISK_ASSISTANT_AI_ENABLED=False)
    def test_permissions_and_review_flow(self):
        with patch('supporthub.telegram_events.queue_risk_assistant_digest'):
            run_daily(client=None)
        insight = RiskInsight.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('risk-assistant', urlconf='passing.urls_tenant')).status_code, 403)
        self.assertEqual(self.client.post(reverse('risk-assistant-action', args=[insight.pk], urlconf='passing.urls_tenant'), {'action': 'review'}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('risk-assistant', urlconf='passing.urls_tenant')).status_code, 200)
        self.assertContains(self.client.get(reverse('risk-assistant', urlconf='passing.urls_tenant')), 'Próximo paso')
        self.assertEqual(self.client.post(reverse('risk-assistant-action', args=[insight.pk], urlconf='passing.urls_tenant'), {'action': 'review'}).status_code, 302)
        insight.refresh_from_db()
        self.assertEqual(insight.status, RiskInsight.Status.REVIEWED)
        self.assertEqual(insight.reviewed_by, self.admin)

    def test_telegram_digest_requires_subscription(self):
        from supporthub.telegram_events import _message, queue_risk_assistant_digest
        recipient = TelegramRecipient.objects.create(user=self.admin, chat_id=10001, notify_risks=False)
        queue_risk_assistant_digest(123)
        self.assertFalse(TelegramEventDelivery.objects.exists())
        recipient.notify_risks = True
        recipient.save(update_fields=['notify_risks'])
        queue_risk_assistant_digest(123)
        self.assertEqual(TelegramEventDelivery.objects.count(), 1)
        with patch('supporthub.telegram_events.queue_risk_assistant_digest'):
            run = run_daily(use_ai=False)
        delivery = TelegramEventDelivery.objects.first()
        delivery.source_id = run.pk
        with patch('supporthub.telegram_events._absolute_url', return_value='https://passing.example/assistant/'):
            message = _message(delivery)
        self.assertIn(run.digest_text, message)
        self.assertIn('https://passing.example/assistant/', message)

    @override_settings(RISK_ASSISTANT_AI_ENABLED=False)
    def test_preview_sends_only_to_current_subscribed_user(self):
        with patch('supporthub.telegram_events.queue_risk_assistant_digest'):
            run = run_daily(use_ai=False)
        url = reverse('risk-assistant-telegram-preview', urlconf='passing.urls_tenant')
        recipient = TelegramRecipient.objects.create(user=self.admin, chat_id=10002, notify_risks=False)
        self.client.force_login(self.other)
        with patch('resources.risk_assistant_views._telegram_call') as send:
            self.assertEqual(self.client.post(url).status_code, 403)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.post(url).status_code, 302)
            send.assert_not_called()
            recipient.notify_risks = True
            recipient.save(update_fields=['notify_risks'])
            cache.delete(f'risk_telegram_preview:{connection.schema_name}:{self.admin.pk}')
            with patch('supporthub.telegram_events._absolute_url', return_value='https://passing.example/assistant/'):
                self.assertContains(self.client.get(reverse('risk-assistant', urlconf='passing.urls_tenant')), 'Enviar prueba a mi Telegram')
                self.assertEqual(self.client.post(url).status_code, 302)
                self.assertEqual(self.client.post(url).status_code, 302)
            send.assert_called_once()
            payload = send.call_args.args[1]
            self.assertEqual(payload['chat_id'], recipient.chat_id)
            self.assertIn(run.digest_text, payload['text'])
        cache.delete(f'risk_telegram_preview:{connection.schema_name}:{self.admin.pk}')
