"""Webhook directory discovery: minimal output, permissions and bounded pages."""

from unittest.mock import patch
from cryptography.fernet import Fernet
from django.test import RequestFactory, override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser
from .bitrix_directory import list_groups, list_people
from .forms import ChatForm
from .models import BitrixPortal, SupportChat, SupportMessage, SupportNotice
from .services import SupportIntegrationError
from .views import bitrix_directory


@override_settings(CRYPTOGRAPHY_KEY=Fernet.generate_key())
class BitrixDirectoryTests(TenantTestCase):
    def setUp(self):
        self.portal = BitrixPortal(name='Prueba', base_url='https://cliente.bitrix24.com')
        self.portal.set_webhook('https://cliente.bitrix24.com/rest/23/private_token_123/')
        self.portal.save()
        self.admin = CustomUser.objects.create_user(username='directory-admin', email='directory-admin@example.test', client=self.tenant, is_superuser=True)
        self.reader = CustomUser.objects.create_user(username='directory-reader', email='directory-reader@example.test', client=self.tenant)
        self.factory = RequestFactory()

    def request(self, data, user=None):
        request = self.factory.post('/', data)
        request.user = user or self.admin
        return request

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_recent_groups_discard_messages_and_private_dialogs(self, call):
        call.return_value = {'items': [
            {'id': 'chat25', 'type': 'chat', 'title': 'Soporte cliente', 'message': {'text': 'DO NOT RETURN', 'date': '2026-10-21T10:00:00+03:00'}, 'avatar': 'https://private.example.test'},
            {'id': '42', 'type': 'user', 'title': 'Private person'},
        ], 'hasMore': False}
        result = list_groups(self.portal)
        self.assertEqual(result, {'items': [{'id': 'chat25', 'name': 'Soporte cliente', 'link': 'https://cliente.bitrix24.com/online/?IM_DIALOG=chat25'}], 'next_offset': None, 'next_cursor': None})
        self.assertEqual(call.call_args.args[1], 'im.recent.list')
        self.assertEqual(call.call_args.args[2]['SKIP_DIALOG'], 'Y')
        self.assertNotIn('DO NOT RETURN', str(result))
        self.assertNotIn('private_token', str(result))
        self.assertFalse(SupportMessage.objects.exists())
        self.assertFalse(SupportNotice.objects.exists())

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_recent_groups_follow_timestamp_cursor(self, call):
        call.return_value = {'items': [{'id': 'chat25', 'title': 'Soporte', 'message': {'date': '2026-10-21T10:00:00+03:00'}}], 'hasMore': True}
        first = list_groups(self.portal)
        list_groups(self.portal, cursor=first['next_cursor'])
        self.assertEqual(call.call_args.args[2]['LAST_MESSAGE_DATE'], '2026-10-21T10:00:00+03:00')

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_group_search_uses_numeric_id_and_page_offset(self, call):
        call.return_value = [{'id': number, 'name': f'Equipo {number}'} for number in range(1, 51)]
        result = list_groups(self.portal, query='Equipo', offset=50)
        self.assertEqual(call.call_args.args[1:], ('im.search.chat.list', {'FIND': 'Equipo', 'OFFSET': 50, 'LIMIT': 50}))
        self.assertEqual(result['items'][0]['id'], 'chat1')
        self.assertEqual(result['next_offset'], 100)
        self.assertEqual(len(result['items']), 50)

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_participants_return_only_human_names_and_ids(self, call):
        call.return_value = [
            {'id': 24, 'name': 'Nicolás', 'email': 'not-returned@example.test', 'phones': ['private']},
            {'id': 25, 'name': 'Bot', 'bot': True},
            {'id': -1, 'name': 'Invalid'},
        ]
        result = list_people(self.portal, dialog='chat25')
        self.assertEqual(result, {'items': [{'id': '24', 'name': 'Nicolás'}], 'next_offset': None})
        self.assertEqual(call.call_args.args[1], 'im.dialog.users.list')
        self.assertEqual(call.call_args.args[2]['DIALOG_ID'], 'chat25')

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_user_search_supports_result_keyed_by_id(self, call):
        call.return_value = {'24': {'id': 24, 'name': 'Nicolás', 'birthday': 'private'}}
        result = list_people(self.portal, query='Nico')
        self.assertEqual(result['items'], [{'id': '24', 'name': 'Nicolás'}])
        self.assertEqual(call.call_args.args[1], 'im.search.user.list')
        self.assertEqual(call.call_args.args[2]['FIND'], 'Nico')

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_discovery_requires_create_or_edit_permission(self, call):
        with patch.object(self.reader, 'has_perm', side_effect=lambda code: code == 'supporthub.view_support_inbox'):
            response = bitrix_directory(self.request({'kind': 'groups'}, self.reader), self.portal.pk)
        self.assertEqual(response.status_code, 403)
        call.assert_not_called()
        call.return_value = {'items': []}
        with patch.object(self.reader, 'has_perm', side_effect=lambda code: code == 'supporthub.create_support'):
            response = bitrix_directory(self.request({'kind': 'groups'}, self.reader), self.portal.pk)
        self.assertEqual(response.status_code, 200)

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_invalid_queries_never_call_bitrix(self, call):
        for data in [
            {'kind': 'people'}, {'kind': 'groups', 'query': 'a'},
            {'kind': 'groups', 'offset': '999999'}, {'kind': 'people', 'dialog': 'https://other.example.test'},
            {'kind': 'groups', 'query': 'a' * 101}, {'kind': 'unknown'},
        ]:
            with self.subTest(data=data):
                self.assertEqual(bitrix_directory(self.request(data), self.portal.pk).status_code, 400)
        call.assert_not_called()

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_read_only_endpoint_has_no_cache_and_does_not_change_polling(self, call):
        call.return_value = {'items': [{'id': 'chat25', 'title': 'Grupo', 'message': {'text': 'private message'}}]}
        response = bitrix_directory(self.request({'kind': 'groups'}), self.portal.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotIn(b'private message', response.content)
        self.assertNotIn(b'private_token', response.content)
        self.portal.refresh_from_db()
        self.assertIsNone(self.portal.subscribed_at)
        self.assertIsNone(self.portal.next_offset)
        self.assertIsNone(self.portal.last_polled_at)

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_safe_integration_errors_and_invalid_response_are_actionable(self, call):
        call.side_effect = SupportIntegrationError('Bitrix24 no permite la consulta; revisá el permiso im.')
        response = bitrix_directory(self.request({'kind': 'groups'}), self.portal.pk)
        self.assertEqual(response.status_code, 502)
        self.assertIn('permiso im', response.content.decode())
        call.side_effect = None
        call.return_value = 'unexpected-private-content'
        response = bitrix_directory(self.request({'kind': 'groups'}), self.portal.pk)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(b'unexpected-private-content', response.content)

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_csrf_and_post_are_required(self, call):
        client = TenantClient(self.tenant, enforce_csrf_checks=True)
        client.force_login(self.admin)
        url = f'/support/portals/{self.portal.pk}/directory/'
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url, {'kind': 'groups'}).status_code, 403)
        call.assert_not_called()

    @patch('supporthub.bitrix_directory._bitrix_call')
    def test_chat_form_contains_directory_without_exposing_webhook(self, call):
        client = TenantClient(self.tenant)
        client.force_login(self.admin)
        response = client.get('/support/chats/new/')
        self.assertContains(response, 'Consultar grupos recientes')
        self.assertContains(response, 'Consultar participantes del grupo')
        self.assertContains(response, 'bitrix-portal-origins')
        self.assertNotContains(response, 'private_token')
        call.assert_not_called()

    def test_group_link_is_generated_for_existing_chats_without_custom_link(self):
        chat = SupportChat.objects.create(portal=self.portal, label='Soporte', dialog_id='chat25')
        self.assertEqual(chat.open_url, 'https://cliente.bitrix24.com/online/?IM_DIALOG=chat25')
        chat.link_url = 'https://cliente.bitrix24.com/online/?IM_DIALOG=chat25&IM_MESSAGE=100'
        self.assertEqual(chat.open_url, chat.link_url)
        form = ChatForm(data={'portal': self.portal.pk, 'label': 'Soporte 2', 'dialog_id': 'chat26', 'ignored_sender_ids': '24, 31', 'enabled': True})
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.ignored_ids, {24, 31})
        self.assertEqual(saved.open_url, 'https://cliente.bitrix24.com/online/?IM_DIALOG=chat26')
