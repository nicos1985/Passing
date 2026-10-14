import logging
from datetime import timedelta, timezone as datetime_timezone
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import override_settings
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser
from passing.logging_utils import RedactingFilter
from .forms import BotTokenForm, PortalForm, ShiftForm
from .models import BitrixPortal, DutyShift, SupportChat, SupportMessage, SupportNotice, TelegramBotConfig, TelegramRecipient, TelegramEventDelivery
from .services import dispatch_notices, get_telegram_token, list_private_telegram_chats, poll_portal
from .telegram_events import queue_monitoring_event, queue_password_request, dispatch_event_deliveries


@override_settings(CRYPTOGRAPHY_KEY=Fernet.generate_key())
class SupportHubTests(TenantTestCase):
    def setUp(self):
        self.portal = BitrixPortal(name='Cliente A', base_url='https://cliente.bitrix24.com')
        self.portal.set_webhook('https://cliente.bitrix24.com/rest/23/test_token_123/')
        self.portal.save()
        self.chat = SupportChat.objects.create(portal=self.portal, label='Soporte general', dialog_id='chat5')

    def _event(self, message_id, dialog='chat5', author=42):
        return {'type': 'ONIMV2MESSAGEADD', 'date': timezone.now().isoformat(), 'data': {
            'message': {'id': message_id, 'authorId': author, 'isSystem': False},
            'chat': {'dialogId': dialog}, 'user': {'bot': False},
        }}

    def test_portal_form_rejects_webhook_from_another_host(self):
        form = PortalForm(data={
            'name': 'Cliente B', 'base_url': 'https://cliente.bitrix24.com',
            'webhook_url': 'https://otro.bitrix24.com/rest/1/test_token_123/', 'enabled': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('webhook_url', form.errors)

    def test_http_logs_redact_bitrix_and_telegram_secrets(self):
        bitrix_secret = 'SyntheticBitrixToken123'
        telegram_secret = '123456:SyntheticTelegramToken'
        record = logging.LogRecord(
            'urllib3.connectionpool', logging.DEBUG, __file__, 1,
            'POST /rest/11/%s/im.v2.Event.get y /bot%s/sendMessage',
            (bitrix_secret, telegram_secret), None,
        )
        RedactingFilter().filter(record)
        self.assertNotIn(bitrix_secret, record.getMessage())
        self.assertNotIn(telegram_secret, record.getMessage())
        self.assertIn('[REDACTED]', record.getMessage())

    def test_bot_token_is_encrypted_and_takes_priority_over_environment(self):
        token = '123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd'
        form = BotTokenForm(data={'token': token})
        self.assertTrue(form.is_valid(), form.errors)
        config = TelegramBotConfig(pk=1)
        config.set_token(form.cleaned_data['token'])
        config.save()
        self.assertNotIn(token, config.token_encrypted)
        with patch.dict('os.environ', {'SUPPORT_TELEGRAM_BOT_TOKEN': '999999:old_token'}):
            self.assertEqual(get_telegram_token(), token)
        self.assertNotIn(token, BotTokenForm().as_p())

    def test_discovery_returns_only_private_chat_identity(self):
        updates = [
            {'message': {'chat': {'id': 123, 'type': 'private', 'first_name': 'Ana', 'username': 'ana'},
                         'text': 'contenido confidencial'}},
            {'message': {'chat': {'id': -321, 'type': 'group', 'title': 'Grupo'}, 'text': 'otro secreto'}},
        ]
        with patch('supporthub.services._telegram_call', return_value=updates):
            chats = list_private_telegram_chats()
        self.assertEqual(chats, [{'id': 123, 'name': 'Ana', 'username': 'ana'}])
        self.assertNotIn('contenido confidencial', str(chats))

    def test_admin_can_save_bot_token_from_passing(self):
        admin = CustomUser.objects.create_user(
            username='admin_soporte', email='admin@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        client = TenantClient(self.tenant)
        client.force_login(admin)
        token = '123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd'
        response = client.post('/support/telegram/bot/', {'token': token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TelegramBotConfig.objects.get(pk=1).token(), token)
        response = client.get('/support/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, token)

    def test_polls_selected_group_without_storing_content_and_deduplicates(self):
        events = [self._event(100), self._event(101), self._event(102, dialog='chat99'), self._event(103, author=23)]
        events[0]['data']['message']['text'] = 'secreto que no debe persistirse'
        with patch('supporthub.services._bitrix_call', side_effect=[True, {'events': events, 'nextOffset': 104, 'hasMore': False}]):
            self.assertEqual(poll_portal(self.portal), 2)
        self.portal.refresh_from_db()
        self.assertEqual(self.portal.next_offset, 104)
        self.assertEqual(SupportMessage.objects.count(), 2)
        notice = SupportNotice.objects.get()
        self.assertEqual(notice.message_count, 2)
        self.assertNotIn('secreto que no debe persistirse', str(notice.__dict__))
        with patch('supporthub.services._bitrix_call', return_value={'events': events, 'nextOffset': 104, 'hasMore': False}):
            self.assertEqual(poll_portal(self.portal), 0)
        self.assertEqual(SupportMessage.objects.count(), 2)

    def test_telegram_delivery_uses_argentina_and_link_without_body(self):
        user = CustomUser.objects.create_user(username='guardia', email='guardia@example.test', password='example-secret', client=self.tenant)
        recipient = TelegramRecipient.objects.create(user=user, chat_id=12345678)
        now = timezone.now()
        DutyShift.objects.create(starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2), primary=recipient)
        SupportNotice.objects.create(chat=self.chat, first_at=now, last_at=now,
                                     notify_after=now - timedelta(seconds=1), message_count=3)
        with patch.dict('os.environ', {'SUPPORT_TELEGRAM_BOT_TOKEN': 'test-token'}), \
             patch('supporthub.services._post_json', return_value={'ok': True}) as post:
            dispatch_notices()
        notice = SupportNotice.objects.get()
        self.assertEqual(notice.status, SupportNotice.Status.SENT)
        self.assertEqual(notice.deliveries.get().recipient, recipient)
        payload = post.call_args.args[1]
        self.assertIn('3 mensajes nuevos', payload['text'])
        self.assertIn('Argentina', payload['text'])
        self.assertIn(self.portal.base_url, payload['text'])
        self.assertNotIn('test-token', payload['text'])

    def test_shift_form_interprets_wall_time_in_argentina(self):
        user = CustomUser.objects.create_user(username='turno', email='turno@example.test', password='example-secret', client=self.tenant)
        recipient = TelegramRecipient.objects.create(user=user, chat_id=9876543)
        form = ShiftForm(data={
            'starts_at': '2026-10-10T10:00', 'ends_at': '2026-10-11T10:00',
            'primary': recipient.pk, 'backup': '', 'note': 'Fin de semana',
        })
        self.assertTrue(form.is_valid(), form.errors)
        shift = form.save()
        self.assertEqual(shift.starts_at.utcoffset().total_seconds(), -10800)
        self.assertEqual(shift.starts_at.astimezone(datetime_timezone.utc).hour, 13)

        overlap = ShiftForm(data={
            'starts_at': '2026-10-10T11:00', 'ends_at': '2026-10-10T12:00',
            'primary': recipient.pk, 'backup': '', 'note': '',
        })
        self.assertFalse(overlap.is_valid())
        self.assertIn('starts_at', overlap.errors)

    def test_backup_receives_after_primary_failure(self):
        primary_user = CustomUser.objects.create_user(
            username='principal', email='principal@example.test', password='example-secret', client=self.tenant,
        )
        backup_user = CustomUser.objects.create_user(
            username='suplente', email='suplente@example.test', password='example-secret', client=self.tenant,
        )
        primary = TelegramRecipient.objects.create(user=primary_user, chat_id=111)
        backup = TelegramRecipient.objects.create(user=backup_user, chat_id=222)
        now = timezone.now()
        DutyShift.objects.create(starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2),
                                 primary=primary, backup=backup)
        notice = SupportNotice.objects.create(chat=self.chat, first_at=now, last_at=now,
                                              notify_after=now - timedelta(seconds=1))
        from .services import SupportIntegrationError
        with patch.dict('os.environ', {'SUPPORT_TELEGRAM_BOT_TOKEN': 'test-token'}), \
             patch('supporthub.services._post_json', side_effect=[SupportIntegrationError('Rechazado'), {'ok': True}]):
            dispatch_notices()
            dispatch_notices()
        notice.refresh_from_db()
        self.assertEqual(notice.status, SupportNotice.Status.SENT)
        self.assertEqual(notice.deliveries.get(recipient=backup).status, SupportNotice.Status.SENT)

    def test_profile_chat_requires_code_before_saving_subscriptions(self):
        user = CustomUser.objects.create_user(
            username='perfil_tg', email='perfil@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        client = TenantClient(self.tenant)
        client.force_login(user)
        with patch('supporthub.telegram_profile._telegram_call') as send:
            response = client.post('/support/telegram/me/link/', {'chat_id': '123456'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TelegramRecipient.objects.filter(user=user).exists())
        code = send.call_args.args[1]['text'].split(': ')[1].split('\n')[0]
        client.post('/support/telegram/me/confirm/', {'code': '00000000' if code != '00000000' else '11111111'})
        self.assertFalse(TelegramRecipient.objects.filter(user=user).exists())
        client.post('/support/telegram/me/confirm/', {'code': code})
        recipient = TelegramRecipient.objects.get(user=user)
        self.assertFalse(recipient.notify_support)
        self.assertFalse(recipient.notify_monitoring)
        client.post('/support/telegram/me/preferences/', {
            'active': 'on', 'notify_support': 'on', 'notify_monitoring': 'on', 'notify_password_requests': 'on',
        })
        recipient.refresh_from_db()
        self.assertTrue(recipient.notify_monitoring)
        self.assertTrue(recipient.notify_password_requests)

    def test_verified_chat_can_be_recovered_from_another_passing_account(self):
        previous = CustomUser.objects.create_user(
            username='vieja_cuenta_tg', email='vieja@example.test', password='example-secret', client=self.tenant,
        )
        current = CustomUser.objects.create_user(
            username='nueva_cuenta_tg', email='nueva@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        recipient = TelegramRecipient.objects.create(
            user=previous, chat_id=998877, active=True, fallback=True,
            notify_support=True, notify_monitoring=True,
        )
        pending = TelegramEventDelivery.objects.create(
            recipient=recipient, category=TelegramEventDelivery.Category.MONITORING,
            source_id=999, event='opened',
        )
        client = TenantClient(self.tenant)
        client.force_login(current)
        with patch('supporthub.telegram_profile._telegram_call') as send:
            response = client.post('/support/telegram/me/link/', {'chat_id': str(recipient.chat_id)})
        self.assertEqual(response.status_code, 302)
        recipient.refresh_from_db()
        self.assertEqual(recipient.user, previous)
        code = send.call_args.args[1]['text'].split(': ')[1].split('\n')[0]
        wrong = client.post('/support/telegram/me/confirm/', {'code': '11111111' if code != '11111111' else '22222222'})
        self.assertEqual(wrong.status_code, 302)
        recipient.refresh_from_db()
        self.assertEqual(recipient.user, previous)
        client.post('/support/telegram/me/confirm/', {'code': code})
        recipient.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(recipient.user, current)
        self.assertFalse(recipient.notify_support)
        self.assertFalse(recipient.notify_monitoring)
        self.assertFalse(recipient.fallback)
        self.assertEqual(pending.status, TelegramEventDelivery.Status.CANCELLED)
        self.assertContains(client.get('/support/telegram/me/'), 'Mis suscripciones')

    def test_event_subscriptions_are_idempotent_and_recheck_eligibility(self):
        user = CustomUser.objects.create_user(
            username='eventos_tg', email='eventos@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        recipient = TelegramRecipient.objects.create(
            user=user, chat_id=123456, notify_monitoring=True, notify_password_requests=True,
        )
        queue_monitoring_event(99999, 'opened')
        queue_monitoring_event(99999, 'opened')
        queue_password_request(99999)
        self.assertEqual(TelegramEventDelivery.objects.count(), 2)
        recipient.notify_monitoring = False
        recipient.save(update_fields=['notify_monitoring'])
        with patch('supporthub.telegram_events._telegram_call') as send:
            dispatch_event_deliveries()
        send.assert_not_called()
        self.assertFalse(TelegramEventDelivery.objects.filter(status='pending').exists())

    def test_support_opt_out_excludes_shift_recipient(self):
        user = CustomUser.objects.create_user(
            username='sin_soporte', email='sin_soporte@example.test', password='example-secret', client=self.tenant,
        )
        recipient = TelegramRecipient.objects.create(user=user, chat_id=321, notify_support=False)
        now = timezone.now()
        DutyShift.objects.create(starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1), primary=recipient)
        from .services import _recipients_for_notice
        selected, backup = _recipients_for_notice(None, now)
        self.assertEqual(selected, [])
        self.assertIsNone(backup)

    def test_monitor_incident_and_recovery_use_same_bot_without_target_details(self):
        from monitoring.models import CheckResult, Monitor
        from monitoring.services import _save_result

        user = CustomUser.objects.create_user(
            username='monitor_tg', email='monitor@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        TelegramRecipient.objects.create(user=user, chat_id=4321, notify_monitoring=True)
        monitor = Monitor.objects.create(
            name='Servicio de prueba', host='https://secret.example.test/path', kind=Monitor.Kind.HTTP,
            failure_threshold=1, recovery_threshold=1,
        )
        _save_result(monitor.pk, CheckResult.Status.FAILURE, 100, 'falló')
        _save_result(monitor.pk, CheckResult.Status.OK, 80, 'bien')
        self.assertEqual(set(TelegramEventDelivery.objects.values_list('event', flat=True)), {'opened', 'recovered'})
        with patch('supporthub.telegram_events._telegram_call') as send:
            dispatch_event_deliveries()
        self.assertEqual(send.call_count, 2)
        for call in send.call_args_list:
            message = call.args[1]['text']
            self.assertIn('Servicio de prueba', message)
            self.assertIn('/monitoring/incidents/', message)
            self.assertNotIn('secret.example.test', message)

    def test_password_request_telegram_contains_only_link(self):
        user = CustomUser.objects.create_user(
            username='admin_password_tg', email='admin_password@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        TelegramRecipient.objects.create(user=user, chat_id=6543, notify_password_requests=True)
        queue_password_request(123)
        with patch('notifications.models.AdminNotification.objects.filter') as notifications, \
             patch('supporthub.telegram_events._telegram_call') as send:
            notifications.return_value.exists.return_value = True
            dispatch_event_deliveries()
        self.assertEqual(send.call_count, 1)
        message = send.call_args.args[1]['text']
        self.assertIn('Nueva solicitud de acceso', message)
        self.assertIn('/notifications/list-notif-admin', message)
        self.assertNotIn('123', message)

    def test_general_settings_contains_bot_configuration_and_support_does_not(self):
        admin = CustomUser.objects.create_user(
            username='admin_config_tg', email='admin_config@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        client = TenantClient(self.tenant)
        client.force_login(admin)
        general = client.get('/login/configuracion-global/')
        self.assertEqual(general.status_code, 200)
        self.assertContains(general, 'Token de BotFather')
        support = client.get('/support/settings/')
        self.assertEqual(support.status_code, 200)
        self.assertNotContains(support, 'Token de BotFather')

    def test_delete_recipient_requires_removing_shifts_first(self):
        admin = CustomUser.objects.create_user(
            username='admin_borrar_tg', email='admin_borrar@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        recipient = TelegramRecipient.objects.create(user=admin, chat_id=8877)
        now = timezone.now()
        shift = DutyShift.objects.create(starts_at=now, ends_at=now + timedelta(hours=2), primary=recipient)
        client = TenantClient(self.tenant)
        client.force_login(admin)
        self.assertEqual(client.get(f'/support/delete/recipient/{recipient.pk}/').status_code, 200)
        client.post(f'/support/delete/recipient/{recipient.pk}/')
        self.assertTrue(TelegramRecipient.objects.filter(pk=recipient.pk).exists())
        client.post(f'/support/delete/shift/{shift.pk}/')
        self.assertFalse(DutyShift.objects.filter(pk=shift.pk).exists())
        client.post(f'/support/delete/recipient/{recipient.pk}/')
        self.assertFalse(TelegramRecipient.objects.filter(pk=recipient.pk).exists())
        self.assertTrue(CustomUser.objects.filter(pk=admin.pk).exists())

    def test_delete_chat_does_not_delete_portal_and_requires_superuser(self):
        staff = CustomUser.objects.create_user(
            username='staff_borrar_tg', email='staff_borrar@example.test', password='example-secret',
            client=self.tenant, is_staff=True,
        )
        client = TenantClient(self.tenant)
        client.force_login(staff)
        self.assertEqual(client.post(f'/support/delete/chat/{self.chat.pk}/').status_code, 403)
        admin = CustomUser.objects.create_user(
            username='admin_chat_tg', email='admin_chat@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        client.force_login(admin)
        self.assertEqual(client.get(f'/support/delete/chat/{self.chat.pk}/').status_code, 200)
        client.post(f'/support/delete/chat/{self.chat.pk}/')
        self.assertFalse(SupportChat.objects.filter(pk=self.chat.pk).exists())
        self.assertTrue(BitrixPortal.objects.filter(pk=self.portal.pk).exists())

    def test_delete_portal_requires_post_and_removes_its_groups(self):
        admin = CustomUser.objects.create_user(
            username='admin_portal_tg', email='admin_portal@example.test', password='example-secret',
            client=self.tenant, is_superuser=True,
        )
        client = TenantClient(self.tenant)
        client.force_login(admin)
        response = client.get(f'/support/delete/portal/{self.portal.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 grupo')
        self.assertTrue(BitrixPortal.objects.filter(pk=self.portal.pk).exists())
        client.post(f'/support/delete/portal/{self.portal.pk}/')
        self.assertFalse(BitrixPortal.objects.filter(pk=self.portal.pk).exists())
        self.assertFalse(SupportChat.objects.filter(pk=self.chat.pk).exists())

    def test_staff_cannot_subscribe_to_password_requests(self):
        staff = CustomUser.objects.create_user(
            username='staff_pref_tg', email='staff_pref@example.test', password='example-secret',
            client=self.tenant, is_staff=True,
        )
        recipient = TelegramRecipient.objects.create(user=staff, chat_id=7773)
        client = TenantClient(self.tenant)
        client.force_login(staff)
        self.assertNotContains(client.get('/support/telegram/me/'), 'name="notify_password_requests"')
        client.post('/support/telegram/me/preferences/', {'active': 'on', 'notify_password_requests': 'on'})
        recipient.refresh_from_db()
        self.assertFalse(recipient.notify_password_requests)

    def test_profile_keeps_user_on_profile_after_saving(self):
        from accounts.models import MultiFactorStatus, TenantSettings

        user = CustomUser.objects.create_user(
            username='perfil_moderno', email='perfil_moderno@example.test', password='example-secret',
            client=self.tenant,
        )
        policy, _ = TenantSettings.objects.get_or_create(client=self.tenant)
        policy.multifactor_status = MultiFactorStatus.OPTIONAL
        policy.save(update_fields=['multifactor_status'])
        client = TenantClient(self.tenant)
        client.force_login(user)
        page = client.get('/login/profile/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Datos personales')
        self.assertContains(page, 'Notificaciones')
        response = client.post('/login/profile/', {
            'first_name': 'Ana', 'last_name': 'Prueba', 'email': user.email,
            'position': 'Soporte', 'language': 'es', 'menu_color': '#205582',
        })
        self.assertRedirects(response, '/login/profile/', fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Ana')
