"""Personal vault privacy, including legacy grants and administrator requests."""

import json
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.http import Http404
from django.db import transaction
from django.urls import set_urlconf, get_urlconf
from django.test import RequestFactory, override_settings
from django_tenants.test.cases import TenantTestCase

from accounts.models import CustomUser
from notifications.models import AdminNotification, UserNotifications
from notifications.views import share_contrasena_form, ListNotificationsAdmin, ListNotificationsUser
from notifications.admin import AdminNotificationsAdmin, UserNotificationsAdmin
from passbase.access import accessible_credentials
from passbase.admin import ContrasenaAdmin, LogDataAdmin
from passbase.forms import ContrasenaUForm
from passbase.models import Contrasena, LogData, SeccionContra
from passbase.views import ContrasListView, ContrasDetailView, ContrasUpdateView, ContrasDeleteView, DescargarArchivo, reveal_credential
from permission.admin import ContraPermissionAdmin, PermissionRolesAdmin
from permission.forms import PermissionRolesForm
from permission.models import ContraPermission, PermissionRoles
from permission.views import grant_permission, generate_rol_permissions, obtener_reporte_contrasenas_repetidas
from passing import settings as project_settings
from supporthub.models import TelegramEventDelivery
from supporthub.telegram_events import _message, queue_password_request


@override_settings(ROOT_URLCONF='passing.urls_tenant')
class PersonalVaultTests(TenantTestCase):
    def setUp(self):
        previous_urlconf = get_urlconf()
        set_urlconf('passing.urls_tenant')
        self.addCleanup(set_urlconf, previous_urlconf)
        crypto = patch.object(project_settings, 'CRYPTOGRAPHY_KEY', Fernet.generate_key())
        crypto.start()
        self.addCleanup(crypto.stop)
        self.owner = CustomUser.objects.create(username='personal-owner', email='owner@example.test', client=self.tenant)
        self.other = CustomUser.objects.create(username='personal-other', email='other@example.test', client=self.tenant)
        self.staff = CustomUser.objects.create(username='personal-staff', email='staff@example.test', client=self.tenant, is_staff=True)
        self.admin = CustomUser.objects.create(username='personal-admin', email='admin@example.test', client=self.tenant, is_staff=True, is_superuser=True)
        self.section = SeccionContra.objects.create(nombre_seccion='Prueba')
        self.personal = Contrasena.objects.create(
            nombre_contra='PERSONAL-PRIVATE-METADATA', seccion=self.section,
            usuario='private-user', contraseña='private-secret', info='private-info',
            link='https://example.test', owner=self.owner, is_personal=True,
        )
        self.corporate = Contrasena.objects.create(
            nombre_contra='CORPORATE', seccion=self.section, usuario='corporate-user',
            contraseña='corporate-secret', owner=self.owner,
        )
        # Simulate stale permissions from before the privacy fix, bypassing forms.
        ContraPermission.objects.bulk_create([
            ContraPermission(user_id=user, contra_id=entry, permission=True, perm_active=True)
            for user in (self.other, self.staff, self.admin)
            for entry in (self.personal, self.corporate)
        ])
        self.factory = RequestFactory()

    def request(self, user, method='get', data=None):
        request = getattr(self.factory, method)('/', data or {})
        request.user = user
        return request

    def test_legacy_grant_never_exposes_personal_to_other_users_or_admins(self):
        for user in (self.other, self.staff, self.admin):
            with self.subTest(user=user.username):
                queryset = accessible_credentials(user)
                self.assertNotIn(self.personal, queryset)
                self.assertIn(self.corporate, queryset)
                response = ContrasListView.as_view()(self.request(user))
                response.render()
                self.assertNotIn(b'PERSONAL-PRIVATE-METADATA', response.content)
                for view in (ContrasDetailView, ContrasUpdateView, DescargarArchivo, ContrasDeleteView):
                    with self.subTest(view=view.__name__):
                        with self.assertRaises(Http404):
                            view.as_view()(self.request(user), pk=self.personal.pk)
                with self.assertRaises(Http404):
                    reveal_credential(self.request(user, 'post', {'field': 'password'}), self.personal.pk)
                with self.assertRaises(Http404):
                    ContrasUpdateView.as_view()(self.request(user, 'post', {'is_personal': False}), pk=self.personal.pk)

    def test_owner_can_view_and_reveal_personal_including_admin_owner(self):
        self.assertIn(self.personal, accessible_credentials(self.owner))
        detail = ContrasDetailView.as_view()(self.request(self.owner), pk=self.personal.pk)
        detail.render()
        self.assertContains(detail, 'PERSONAL-PRIVATE-METADATA')
        self.assertNotContains(detail, self.other.username)
        for user in (self.owner, self.admin):
            if user == self.admin:
                self.personal.owner = user
                self.personal.save(update_fields=['owner'])
            response = reveal_credential(self.request(user, 'post', {'field': 'password'}), self.personal.pk)
            self.assertEqual(json.loads(response.content), {'value': 'private-secret'})

    @patch('notifications.views.queue_password_request')
    def test_personal_cannot_be_requested_for_sharing_even_by_owner_or_admin(self, queue):
        for user in (self.owner, self.other, self.staff, self.admin):
            for method in ('get', 'post'):
                with self.assertRaises(Http404):
                    share_contrasena_form(self.request(user, method, {'id_user_share': self.other.pk}), self.personal.pk)
        queue.assert_not_called()
        self.assertFalse(AdminNotification.objects.exists())

    def test_admin_cannot_approve_an_old_personal_request(self):
        with self.assertRaises(Http404):
            grant_permission(self.request(self.admin), self.personal.pk, self.other.pk, 999, self.owner.username)

    def test_personal_is_not_selectable_in_role_forms_or_django_admin(self):
        form = PermissionRolesForm(data={'rol_name': 'Invalid role', 'contrasenas': [self.personal.pk]})
        self.assertFalse(form.is_valid())
        self.assertIn('contrasenas', form.errors)
        site = AdminSite()
        request = self.request(self.admin)
        permission_admin = ContraPermissionAdmin(ContraPermission, site)
        field = permission_admin.formfield_for_foreignkey(ContraPermission._meta.get_field('contra_id'), request)
        self.assertNotIn(self.personal, field.queryset)
        role_admin = PermissionRolesAdmin(PermissionRoles, site)
        field = role_admin.formfield_for_manytomany(PermissionRoles._meta.get_field('contrasenas'), request)
        self.assertNotIn(self.personal, field.queryset)

    def test_model_relation_rejects_personal_role_assignment_both_directions(self):
        role = PermissionRoles.objects.create(rol_name='No personal')
        with self.assertRaises(ValidationError), transaction.atomic():
            role.contrasenas.add(self.personal)
        with self.assertRaises(ValidationError), transaction.atomic():
            self.personal.roles.add(role)
        self.assertFalse(role.contrasenas.exists())

    def test_legacy_role_link_does_not_grant_personal_access(self):
        role = PermissionRoles.objects.create(rol_name='Legacy personal')
        through = PermissionRoles.contrasenas.through
        through.objects.bulk_create([through(permissionroles=role, contrasena=self.personal)])
        ContraPermission.objects.filter(user_id=self.other, contra_id=self.personal).delete()
        generate_rol_permissions(self.request(self.admin), role, self.other)
        self.assertFalse(ContraPermission.objects.filter(user_id=self.other, contra_id=self.personal).exists())
        self.assertNotIn(self.personal, role.get_contrasenas())

    def test_becoming_personal_removes_external_permissions_and_roles(self):
        role = PermissionRoles.objects.create(rol_name='Before personal')
        role.contrasenas.add(self.corporate)
        self.corporate.is_personal = True
        self.corporate.save(update_fields=['is_personal'])
        self.assertFalse(ContraPermission.objects.filter(contra_id=self.corporate).exclude(user_id=self.owner).exists())
        self.assertFalse(role.contrasenas.exists())
        self.assertIn(self.corporate, accessible_credentials(self.owner))

    def test_nonowner_cannot_change_privacy_on_shared_credential(self):
        form = ContrasenaUForm(instance=self.corporate, actor=self.other)
        self.assertTrue(form.fields['is_personal'].disabled)
        form = ContrasenaUForm(instance=self.corporate, actor=self.owner)
        self.assertFalse(form.fields['is_personal'].disabled)

    def test_audit_does_not_decrypt_personal_credentials(self):
        original = Contrasena.get_decrypted_password
        def decrypt(entry):
            if entry.is_personal:
                raise AssertionError('personal credential reached admin audit')
            return original(entry)
        with patch.object(Contrasena, 'get_decrypted_password', autospec=True, side_effect=decrypt) as decrypt_mock:
            report = obtener_reporte_contrasenas_repetidas()
        self.assertEqual([call.args[0].pk for call in decrypt_mock.call_args_list], [self.corporate.pk])
        self.assertEqual(report['resumen_total_duplicados'], 0)

    def test_django_admin_hides_other_owners_personals_and_audit_logs(self):
        request = self.request(self.admin)
        site = AdminSite()
        admin = ContrasenaAdmin(Contrasena, site)
        self.assertNotIn(self.personal, admin.get_queryset(request))
        self.assertIsNone(admin.get_object(request, str(self.personal.pk)))
        self.assertNotIn(self.personal.pk, ContraPermissionAdmin(ContraPermission, site).get_queryset(request).values_list('contra_id', flat=True))
        personal_log = LogData.objects.get(contraseña=self.personal.pk)
        self.assertNotIn(personal_log, LogDataAdmin(LogData, site).get_queryset(request))

    def test_old_personal_notifications_are_hidden_and_telegram_cancelled(self):
        notification = AdminNotification.objects.create(
            id_contrasena=self.personal, id_user=self.owner.username, id_user_share=self.other,
            type_notification='Compartir Contraseña', action='Permiso', comment='legacy',
        )
        user_notice = UserNotifications.objects.create(
            id_contrasena=self.personal, id_user=self.other, type_notification='legacy', comment='legacy',
        )
        admin_view = ListNotificationsAdmin()
        admin_view.request = self.request(self.admin)
        self.assertNotIn(notification, admin_view.get_queryset())
        user_view = ListNotificationsUser()
        user_view.request = self.request(self.other)
        self.assertNotIn(user_notice, user_view.get_queryset())
        site = AdminSite()
        self.assertNotIn(notification, AdminNotificationsAdmin(AdminNotification, site).get_queryset(self.request(self.admin)))
        self.assertNotIn(user_notice, UserNotificationsAdmin(UserNotifications, site).get_queryset(self.request(self.admin)))
        with patch('supporthub.telegram_events._queue') as queue:
            queue_password_request(notification.pk)
        queue.assert_not_called()
        delivery = TelegramEventDelivery(category=TelegramEventDelivery.Category.PASSWORD_REQUEST, source_id=notification.pk)
        self.assertIsNone(_message(delivery))

    def test_making_legacy_personal_corporate_does_not_resurrect_old_grants(self):
        self.personal.is_personal = False
        self.personal.save(update_fields=['is_personal'])
        self.assertFalse(ContraPermission.objects.filter(contra_id=self.personal).exclude(user_id=self.owner).exists())
        self.assertNotIn(self.personal, accessible_credentials(self.other))

    def test_attachment_is_only_readable_by_personal_owner(self):
        from tempfile import TemporaryDirectory
        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage
        with TemporaryDirectory() as temporary:
            with patch.object(Contrasena._meta.get_field('file'), 'storage', FileSystemStorage(location=temporary)):
                self.personal.file.storage = Contrasena._meta.get_field('file').storage
                self.personal.file.save('personal.txt', ContentFile(b'owner only'), save=True)
                response = DescargarArchivo.as_view()(self.request(self.owner), pk=self.personal.pk)
                self.assertEqual(response.content, b'owner only')
                for user in (self.other, self.staff, self.admin):
                    with self.assertRaises(Http404):
                        DescargarArchivo.as_view()(self.request(user), pk=self.personal.pk)

    @patch('notifications.views.queue_password_request')
    def test_corporate_sharing_still_works_for_an_authorized_user(self, queue):
        from django.contrib.messages.storage.fallback import FallbackStorage
        target = CustomUser.objects.create(username='share-target', email='target@example.test', client=self.tenant)
        request = self.request(self.owner, 'post', {'id_user_share': target.pk, 'comment': 'Corporate sharing'})
        request.session = {}
        request._messages = FallbackStorage(request)
        response = share_contrasena_form(request, self.corporate.pk)
        self.assertEqual(response.status_code, 302)
        notification = AdminNotification.objects.get(id_contrasena=self.corporate, id_user_share=target)
        queue.assert_called_once_with(notification.pk)

    def test_nonowner_without_grant_cannot_request_corporate_sharing(self):
        outsider = CustomUser.objects.create(username='no-access', email='no-access@example.test', client=self.tenant)
        with self.assertRaises(Http404):
            share_contrasena_form(self.request(outsider, 'post', {'id_user_share': self.other.pk}), self.corporate.pk)
