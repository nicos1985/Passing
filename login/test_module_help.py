from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from accounts.models import CustomUser, TenantMembership
from passing.help_content import HELP_ORDER


class ModuleHelpTests(TenantTestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username="help-admin", email="help-admin@example.test", password="test-password",
        )
        self.admin.client = self.tenant
        self.admin.save(update_fields=["client"])
        TenantMembership.objects.create(user=self.admin, client=self.tenant, is_active=True)
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.admin)

    def test_every_main_module_has_a_help_page(self):
        for slug in HELP_ORDER:
            with self.subTest(slug=slug):
                response = self.client.get(f"/help/{slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Flujo recomendado")

    def test_overview_links_to_the_module_guides(self):
        response = self.client.get("/help/inicio/")
        for slug in HELP_ORDER[1:]:
            self.assertContains(response, f"/help/{slug}/")

    def test_help_respects_module_access(self):
        user = CustomUser.objects.create_user(
            username="help-reader", email="help-reader@example.test",
            password="test-password", client=self.tenant,
        )
        TenantMembership.objects.create(user=user, client=self.tenant, is_active=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/help/inicio/").status_code, 200)
        self.assertEqual(self.client.get("/help/configuracion/").status_code, 403)
        self.assertEqual(self.client.get("/help/riesgos/").status_code, 403)
