"""La campanita muestra solo avisos del usuario y evita duplicados por canal."""

from django.test import override_settings
from unittest.mock import patch
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser
from .models import InboxNotification
from .service import record_inbox_notice


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationInboxTests(TenantTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='bell_user', email='bell@example.test', password='test-password', client=self.tenant,
        )
        self.other = CustomUser.objects.create_user(
            username='other_bell', email='other@example.test', password='test-password', client=self.tenant,
        )
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.user)

    def test_two_channels_make_one_private_notification(self):
        for channel in ('telegram', 'email', 'telegram'):
            record_inbox_notice(
                self.user, category='monitoring', source_id=12, event='opened',
                title='Incidente de monitorización', target_path='/monitoring/incidents/12/', channel=channel,
            )
        notice = InboxNotification.objects.get(user=self.user)
        self.assertEqual(notice.channels, 'email,telegram')
        response = self.client.get('/notifications/')
        self.assertContains(response, 'Incidente de monitorización')
        self.assertContains(response, 'Correo')
        self.assertContains(response, 'Telegram')
        self.assertEqual(self.client.post(f'/notifications/open/{notice.pk}/').status_code, 302)
        notice.refresh_from_db()
        self.assertTrue(notice.viewed)

    def test_mark_vistas_requires_csrf_token(self):
        protected_client = TenantClient(self.tenant, enforce_csrf_checks=True)
        protected_client.force_login(self.user)
        page = protected_client.get('/notifications/list-notif-user')
        self.assertEqual(page.status_code, 200)
        response = protected_client.post(
            '/notifications/marcar-vistas/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_open_another_users_notice(self):
        notice = record_inbox_notice(
            self.other, category='support', source_id=8, event='message',
            title='Nuevo aviso de soporte', channel='telegram',
        )
        self.assertNotContains(self.client.get('/notifications/'), 'Nuevo aviso de soporte')
        self.assertEqual(self.client.post(f'/notifications/open/{notice.pk}/').status_code, 404)
        self.assertFalse(InboxNotification.objects.get(pk=notice.pk).viewed)

    def test_only_superuser_can_manage_channels_and_email_test_goes_to_self(self):
        from django.core import mail

        self.assertEqual(self.client.get('/notifications/settings/').status_code, 403)
        self.assertEqual(self.client.post('/notifications/settings/test-email/').status_code, 403)
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.assertEqual(self.client.get('/notifications/settings/').status_code, 200)
        self.assertEqual(self.client.post('/notifications/settings/test-email/').status_code, 302)
        self.assertEqual(mail.outbox[-1].to, ['bell@example.test'])
        self.assertEqual(self.client.get('/update_email_config/').status_code, 404)
        self.assertEqual(self.client.get('/test_send_email/').status_code, 404)

    @patch('monitoring.deliveries.get_connection')
    @patch('monitoring.deliveries.send_mail', return_value=1)
    def test_monitoring_email_is_reflected_without_storing_host(self, send_mail_mock, connection_mock):
        from monitoring.deliveries import _send_email
        from monitoring.models import Delivery, Incident, Monitor

        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        monitor = Monitor.objects.create(
            name='Prueba privada', host='private.example.test', recipients='bell@example.test',
        )
        incident = Incident.objects.create(monitor=monitor)
        delivery = Delivery.objects.create(incident=incident, channel=Delivery.Channel.EMAIL, event='opened')
        _send_email(delivery)
        send_mail_mock.assert_called_once()
        notice = InboxNotification.objects.get(user=self.user, category='monitoring')
        self.assertEqual(notice.channels, 'email')
        self.assertNotIn('private.example.test', notice.title)
        self.assertEqual(notice.target_path, f'/monitoring/incidents/{incident.pk}/')
