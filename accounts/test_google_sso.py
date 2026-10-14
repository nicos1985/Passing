"""Verifica el vínculo de Google y el acceso al tenant sin llamar a OAuth externo."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from allauth.core.exceptions import ImmediateHttpResponse
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase

from accounts.adapters import SocialAdapter
from accounts.models import CustomUser, TenantMembership, TenantSettings
from accounts.utils import build_oauth_state
from accounts.views import post_login_redirect


class GoogleSSOTests(TenantTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="google_user", email="google@example.test", password="test-password",
            client=self.tenant,
        )
        TenantMembership.objects.create(user=self.user, client=self.tenant, is_active=True)
        self.policy, _ = TenantSettings.objects.get_or_create(client=self.tenant)
        self.policy.is_active = True
        self.policy.sso_google_enabled = True
        self.policy.sso_autolink_by_email = True
        self.policy.save()
        self.request = RequestFactory().get("/accounts/post-login/")
        self.request.user = self.user
        self.request.session = {}

    def sociallogin(self, *, verified=True, existing=False):
        return SimpleNamespace(
            is_existing=existing,
            user=self.user if existing else SimpleNamespace(email=self.user.email),
            account=SimpleNamespace(provider="google", extra_data={"email": self.user.email}),
            email_addresses=[SimpleNamespace(email=self.user.email, verified=verified)],
            connect=Mock(),
        )

    def test_admin_created_active_user_can_link_verified_google_email(self):
        sociallogin = self.sociallogin()
        SocialAdapter().pre_social_login(self.request, sociallogin)
        sociallogin.connect.assert_called_once_with(self.request, self.user)

    def test_pending_user_cannot_link_google_email(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        sociallogin = self.sociallogin()
        with self.assertRaises(ImmediateHttpResponse):
            SocialAdapter().pre_social_login(self.request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_unverified_email_cannot_link(self):
        sociallogin = self.sociallogin(verified=False)
        with self.assertRaises(ImmediateHttpResponse):
            SocialAdapter().pre_social_login(self.request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_autolink_policy_is_respected(self):
        self.policy.sso_autolink_by_email = False
        self.policy.save(update_fields=["sso_autolink_by_email"])
        sociallogin = self.sociallogin()
        with self.assertRaises(ImmediateHttpResponse):
            SocialAdapter().pre_social_login(self.request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_existing_google_link_still_works_when_autolink_disabled(self):
        self.policy.sso_autolink_by_email = False
        self.policy.save(update_fields=["sso_autolink_by_email"])
        SocialAdapter().pre_social_login(self.request, self.sociallogin(existing=True))

    def test_disabled_google_policy_blocks_existing_link_and_tenant_redirect(self):
        self.policy.sso_google_enabled = False
        self.policy.save(update_fields=["sso_google_enabled"])
        with self.assertRaises(ImmediateHttpResponse):
            SocialAdapter().pre_social_login(self.request, self.sociallogin(existing=True))
        with patch("accounts.views.messages.error"):
            response = post_login_redirect(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("sso/consume", response["Location"])

    def test_explicit_tenant_redirect_rejects_disabled_google_policy(self):
        self.policy.sso_google_enabled = False
        self.policy.save(update_fields=["sso_google_enabled"])
        state = build_oauth_state(self.tenant.schema_name, "/login/home/")
        request = RequestFactory().get("/accounts/post-login/", {"_s": state})
        request.user = self.user
        request.session = {}
        response = post_login_redirect(request)
        self.assertEqual(response.status_code, 403)

    def test_enabled_google_policy_redirects_to_member_tenant(self):
        with patch("accounts.views.redirect_to_tenant_with_token", return_value=HttpResponseRedirect("/ok/")) as handoff:
            response = post_login_redirect(self.request)
        self.assertEqual(response["Location"], "/ok/")
        handoff.assert_called_once_with(self.request, self.user, self.tenant, "/login/home/")
