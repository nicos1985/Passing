from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.test import override_settings
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from threat_intel.management.commands import threatintel_run  # Ensure patch target is imported.

from .forms import ReportForm, SourceForm, TechTagForm
from .models import IntelItem, Report, Run, RunItem, Source, TechTag
from .services.ai import analyze_item
from .services.relevance import mark_relevance_for_run
from .sources.aws_bulletins import AwsBulletinsConnector
from .services.report import build_report_for_run
from .services.emailer import send_report_email_smtp
from .views import RunListView, _safe_csv_cell, search_threats_ajax


class ThreatIntelSecurityTests(TenantTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='intel_reader', email='intel_reader@example.test',
            password='test-password', client=self.tenant,
        )
        self.factory = RequestFactory()

    def test_authenticated_user_without_permissions_cannot_access_module(self):
        request = self.factory.get('/threat-intel/runs/')
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            RunListView.as_view()(request)
        request = self.factory.get('/threat-intel/ajax/search-threats/', {'q': 'test'})
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            search_threats_ajax(request)

    def test_forms_validate_supported_fields_and_recipients(self):
        self.assertIn('is_active', SourceForm().fields)
        self.assertFalse(TechTagForm(data={
            'name': 'Ubuntu Linux', 'keywords': '{"bad": "format"}', 'is_active': 'on',
        }).is_valid())
        form = ReportForm(data={
            'subject': 'Informe', 'body_md': 'Texto',
            'recipients': 'uno@example.test, dos@example.test',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['recipients'], ['uno@example.test', 'dos@example.test'])

    def test_csv_escapes_spreadsheet_formulas_from_feed(self):
        self.assertEqual(_safe_csv_cell('=HYPERLINK("bad")'), '\'=HYPERLINK("bad")')
        self.assertEqual(_safe_csv_cell('CVE-2026-1234'), 'CVE-2026-1234')

    def test_report_escapes_external_content(self):
        now = timezone.now()
        run = Run.objects.create(period_start=now-timedelta(days=1), period_end=now)
        item = IntelItem.objects.create(
            canonical_id='<img src=x onerror=alert(1)>', title='Boletín externo',
            severity='critical', is_relevant=True,
        )
        RunItem.objects.create(run=run, item=item)
        _, body_md, body_html = build_report_for_run(run)
        self.assertIn('<img', body_md)
        self.assertNotIn('<img', body_html)
        self.assertIn('&lt;img', body_html)

    @patch('threat_intel.services.emailer.EmailMultiAlternatives')
    def test_email_html_escapes_report_text(self, mail_class):
        report = Report(subject='Informe', body_md='<script>alert(1)</script>',
                        recipients=['admin@example.test'])
        send_report_email_smtp(report)
        html = mail_class.return_value.attach_alternative.call_args.args[0]
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_relevance_matches_terms_without_substring_false_positives(self):
        TechTag.objects.create(name='Ubuntu Linux', keywords=['node'])
        now = timezone.now()
        run = Run.objects.create(period_start=now-timedelta(days=1), period_end=now)
        item = IntelItem.objects.create(canonical_id='CVE-TEST-2', title='Anode issue')
        RunItem.objects.create(run=run, item=item)
        _, relevant, _ = mark_relevance_for_run(run)
        self.assertEqual(relevant, 0)

    def test_ai_prompt_uses_only_allowlisted_active_technology_names(self):
        TechTag.objects.create(name='Ubuntu Linux', keywords=['ubuntu'])
        TechTag.objects.create(name='private.example.test', keywords=['secret'])
        client = Mock()
        client.create_message.return_value = '{"summary": "ok"}'
        item = IntelItem(canonical_id='CVE-TEST-3', title='Public bulletin')
        analyze_item(client, item, 'test-model', 'v1')
        prompt = client.create_message.call_args.kwargs['system_prompt']
        self.assertIn('Ubuntu Linux', prompt)
        self.assertNotIn('private.example.test', prompt)

    def test_command_requires_explicit_tenant_from_public_schema(self):
        with schema_context('public'), self.assertRaisesRegex(ValueError, '--tenant'):
            call_command('threatintel_run', '--dry-run')

    @patch('threat_intel.sources.aws_bulletins.requests.get')
    def test_aws_connector_uses_timeout_and_parses_feed(self, get):
        response = Mock()
        response.content = b'<rss version="2.0"><channel><title>AWS</title><item><title>Bulletin</title><link>https://aws.amazon.com/security/example</link></item></channel></rss>'
        get.return_value = response
        now = timezone.now()
        items, _ = AwsBulletinsConnector().fetch(now-timedelta(days=1), now)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Bulletin')
        self.assertEqual(get.call_args.kwargs['timeout'], (10, 30))

    @override_settings(THREAT_INTEL={
        'ENABLED_SOURCES': ['NVD'], 'DEFAULT_DAYS': 1,
        'ENABLE_AI_ANALYSIS': False, 'EMAIL_RECIPIENTS': [],
    })
    @patch('threat_intel.management.commands.threatintel_run.NvdConnector.fetch')
    @patch('threat_intel.management.commands.threatintel_run.send_report_email')
    def test_failed_source_does_not_send_or_report_success(self, send_email, fetch):
        Source.objects.create(code='NVD', name='NVD', base_url='https://nvd.nist.gov')
        fetch.side_effect = RuntimeError('test source failure')
        with self.assertRaises(RuntimeError):
            call_command('threatintel_run', '--send-email')
        run = Run.objects.latest('pk')
        self.assertEqual(run.status, 'failed')
        self.assertIn('NVD', run.error)
        send_email.assert_not_called()

    @override_settings(THREAT_INTEL={
        'ENABLED_SOURCES': ['NVD'], 'DEFAULT_DAYS': 1,
        'ENABLE_AI_ANALYSIS': False, 'EMAIL_RECIPIENTS': ['admin@example.test'],
    })
    @patch('threat_intel.management.commands.threatintel_run.NvdConnector.fetch', return_value=([], {}))
    @patch('threat_intel.management.commands.threatintel_run.send_report_email')
    def test_failed_email_is_not_marked_sent(self, send_email, fetch):
        Source.objects.create(code='NVD', name='NVD', base_url='https://nvd.nist.gov')
        send_email.return_value = {'status': 'error', 'message': 'SMTP unavailable'}
        with self.assertRaises(RuntimeError):
            call_command('threatintel_run', '--tenant', self.tenant.schema_name, '--send-email')
        run = Run.objects.latest('pk')
        self.assertEqual(run.status, 'failed')
        self.assertIsNone(Report.objects.get(run=run).sent_at)
