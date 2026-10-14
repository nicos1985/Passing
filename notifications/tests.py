"""La campanita muestra solo avisos del usuario y evita duplicados por canal."""

from django.test import override_settings
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

    def test_user_cannot_open_another_users_notice(self):
        notice = record_inbox_notice(
            self.other, category='support', source_id=8, event='message',
            title='Nuevo aviso de soporte', channel='telegram',
        )
        self.assertNotContains(self.client.get('/notifications/'), 'Nuevo aviso de soporte')
        self.assertEqual(self.client.post(f'/notifications/open/{notice.pk}/').status_code, 404)
        self.assertFalse(InboxNotification.objects.get(pk=notice.pk).viewed)
