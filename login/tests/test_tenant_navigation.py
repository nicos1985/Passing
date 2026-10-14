"""El menú tenant muestra los módulos que cada usuario puede abrir."""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser
from resources.models import RiskEvaluation
from permission.models import PermissionRoles, UserRoles
from permission.forms import PermissionRolesForm, UserRolForm


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TenantNavigationTests(TenantTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='regular_nav', email='regular_nav@example.test',
            password='test-password', client=self.tenant,
        )
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.user)

    def test_logout_clears_tenant_session_and_continues_to_hub(self):
        response = self.client.post('/login/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('/accounts/logout/'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_regular_user_sees_vault_but_not_restricted_modules(self):
        response = self.client.get('/login/home/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="passwordsubmenu"')
        self.assertNotContains(response, 'id="resourcesubmenu"')
        self.assertContains(response, 'href="/notifications/"')
        self.assertNotContains(response, 'id="risksubmenu"')
        self.assertNotContains(response, 'data-sidebar-label="Configuración"')
        self.assertContains(response, 'id="monitoringsubmenu"')
        self.assertContains(response, '/monitoring/status/')
        self.assertNotContains(response, 'href="/monitoring/incidents/"')
        self.assertNotContains(response, 'id="supportsubmenu"')
        self.assertContains(response, 'id="sidebar-toggle"')
        self.assertContains(response, 'data-sidebar-label="Monitorización"')

    def test_resources_read_role_shows_menu_and_blocks_creation(self):
        role = PermissionRoles.objects.create(
            rol_name='Consulta de recursos', module_permissions=['resources_read'],
        )
        UserRoles.objects.create(user=self.user, rol=role)
        response = self.client.get('/login/home/')
        self.assertContains(response, 'id="resourcesubmenu"')
        self.assertEqual(self.client.get('/resources/asset-list/').status_code, 200)
        self.assertEqual(self.client.get('/resources/asset-create/').status_code, 403)
        self.assertTrue(self.user.has_perm('resources.view_vendor'))
        self.assertFalse(self.user.has_perm('resources.add_vendor'))
        role.module_permissions = ['resources_read', 'resources_create']
        role.save(update_fields=['module_permissions'])
        self.assertEqual(self.client.get('/resources/asset-create/').status_code, 200)
        self.assertEqual(self.client.get('/resources/asset-update/999999').status_code, 403)

    def test_risk_permission_reveals_only_matching_links(self):
        content_type = ContentType.objects.get_for_model(RiskEvaluation)
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type, codename='view_riskevaluation',
            defaults={'name': 'Can view risk evaluation'},
        )
        self.user.user_permissions.add(permission)
        response = self.client.get('/login/home/')
        self.assertContains(response, 'id="risksubmenu"')
        self.assertContains(response, '/resources/evaluation-list/')
        self.assertNotContains(response, '/resources/threat-list/')

    def test_module_role_grants_and_revokes_access(self):
        role = PermissionRoles.objects.create(
            rol_name='Analista', module_permissions=['risks_read', 'support_inbox'],
        )
        UserRoles.objects.create(user=self.user, rol=role)
        self.assertTrue(self.user.has_perm('resources.view_riskevaluation'))
        self.assertTrue(self.user.has_perm('supporthub.view_support_inbox'))
        self.assertFalse(self.user.has_perm('resources.change_riskevaluation'))
        response = self.client.get('/login/home/')
        self.assertContains(response, 'id="risksubmenu"')
        self.assertContains(response, 'id="supportsubmenu"')
        self.assertContains(response, 'Bandeja de avisos')
        self.assertNotContains(response, 'Configurar soporte')

        role.module_permissions = []
        role.save(update_fields=['module_permissions'])
        self.assertFalse(self.user.has_perm('resources.view_riskevaluation'))
        self.assertFalse(self.user.has_perm('supporthub.view_support_inbox'))

    def test_staff_cannot_grant_module_access(self):
        staff = CustomUser.objects.create_user(
            username='staff_nav', email='staff_nav@example.test',
            password='test-password', client=self.tenant, is_staff=True,
        )
        form = PermissionRolesForm(
            data={'rol_name': 'Rol nuevo', 'module_permissions': ['risks_read']},
            actor=staff,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['module_permissions'], [])
        privileged = PermissionRoles.objects.create(
            rol_name='Privilegiado', module_permissions=['risks_read'],
        )
        assign_form = UserRolForm(
            data={'user': self.user.pk, 'rol': privileged.pk}, actor=staff,
        )
        self.assertFalse(assign_form.is_valid())

    def test_read_only_monitoring_role_cannot_open_write_forms(self):
        role = PermissionRoles.objects.create(
            rol_name='Observador', module_permissions=['monitoring_read'],
        )
        UserRoles.objects.create(user=self.user, rol=role)
        self.assertEqual(self.client.get('/monitoring/').status_code, 200)
        self.assertEqual(self.client.get('/monitoring/new/').status_code, 403)
        self.assertFalse(self.user.has_perm('monitoring.edit_monitoring'))
        response = self.client.get('/monitoring/')
        self.assertNotContains(response, 'Nuevo monitoreo')
        self.assertContains(response, 'id="monitoringsubmenu"')
        self.assertContains(response, 'href="/monitoring/incidents/"')

    def test_support_actions_are_independent(self):
        role = PermissionRoles.objects.create(
            rol_name='Soporte lector', module_permissions=['support_read'],
        )
        UserRoles.objects.create(user=self.user, rol=role)
        self.assertEqual(self.client.get('/support/').status_code, 200)
        self.assertEqual(self.client.get('/support/settings/').status_code, 403)
        role.module_permissions = ['support_read', 'support_create']
        role.save(update_fields=['module_permissions'])
        self.assertEqual(self.client.get('/support/settings/').status_code, 200)
        self.assertEqual(self.client.get('/support/portals/new/').status_code, 200)
        self.assertEqual(self.client.get('/support/chats/new/').status_code, 200)
        self.assertFalse(self.user.has_perm('supporthub.edit_support'))
        self.assertContains(self.client.get('/login/home/'), 'Configurar soporte')

    def test_superuser_role_editor_shows_action_matrix(self):
        admin = CustomUser.objects.create_user(
            username='admin_roles', email='admin_roles@example.test',
            password='test-password', client=self.tenant,
            is_staff=True, is_superuser=True,
        )
        role = PermissionRoles.objects.create(rol_name='Operador')
        self.client.force_login(admin)
        response = self.client.get(f'/perm/permissionroles-update/{role.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role-permissions-table')
        self.assertContains(response, 'name="module_permissions"')
        self.assertContains(response, '<th scope="row">Recursos</th>')
        page = response.content.decode()
        self.assertLess(page.index('id="monitoringsubmenu"'), page.index('id="supportsubmenu"'))
        self.assertLess(page.index('id="supportsubmenu"'), page.index('data-sidebar-label="Configuración"'))

    def test_edit_permission_also_grants_read_in_role_form(self):
        admin = CustomUser.objects.create_user(
            username='admin_form', email='admin_form@example.test',
            password='test-password', client=self.tenant,
            is_staff=True, is_superuser=True,
        )
        form = PermissionRolesForm(
            data={'rol_name': 'Editor', 'module_permissions': ['monitoring_edit']},
            actor=admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['module_permissions'], ['monitoring_read', 'monitoring_edit'])

    def test_risks_and_intelligence_actions_do_not_cross_grant(self):
        role = PermissionRoles.objects.create(
            rol_name='Analista editor',
            module_permissions=['risks_read', 'risks_create', 'threat_intel_read', 'threat_intel_edit'],
        )
        UserRoles.objects.create(user=self.user, rol=role)
        self.assertTrue(self.user.has_perm('resources.add_riskevaluation'))
        self.assertFalse(self.user.has_perm('resources.change_riskevaluation'))
        self.assertTrue(self.user.has_perm('threat_intel.change_review'))
        self.assertTrue(self.user.has_perm('threat_intel.view_source'))
        self.assertFalse(self.user.has_perm('threat_intel.add_review'))
        self.assertFalse(self.user.has_perm('threat_intel.delete_review'))
