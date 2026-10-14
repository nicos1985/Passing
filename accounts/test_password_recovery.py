"""El hub recupera contraseñas sin revelar si existe un correo."""

import re
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.test import RequestFactory, override_settings
from django.urls import resolve, reverse
from django_tenants.test.cases import TenantTestCase
from django_recaptcha.client import RecaptchaResponse

from accounts.forms import HubLoginForm


@override_settings(
    ROOT_URLCONF="passing.urls_public",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PublicPasswordRecoveryTests(TenantTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="recovery_user", email="recovery@example.test",
            password="old-password", client=self.tenant,
        )
        self.factory = RequestFactory()

    def request(self, method, path, data=None, session=None):
        request = getattr(self.factory, method)(path, data=data or {})
        request.user = AnonymousUser()
        request.session = session if session is not None else {}
        request.urlconf = "passing.urls_public"
        request._dont_enforce_csrf_checks = True
        return request

    def dispatch(self, request):
        match = resolve(request.path, urlconf="passing.urls_public")
        return match.func(request, *match.args, **match.kwargs)

    def test_login_links_to_public_recovery(self):
        response = self.dispatch(self.request("get", "/login/"))
        self.assertContains(response, reverse("accounts:password_reset"))
        self.assertContains(response, 'name="captcha"')

    @patch('django_recaptcha.client.submit', return_value=RecaptchaResponse(True, extra_data={'score': 0.9}, action='password_recovery'))
    def test_known_email_can_reset_password_through_public_hub(self, _captcha):
        reset_path = reverse("accounts:password_reset")
        response = self.dispatch(self.request("post", reset_path, {"email": self.user.email, "captcha": "valid-token"}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"https?://\S+", mail.outbox[0].body).group()
        self.assertTrue(urlsplit(link).path.startswith("/accounts/recover/confirm/"))

        session = {}
        first = self.dispatch(self.request("get", urlsplit(link).path, session=session))
        self.assertEqual(first.status_code, 302)
        confirm_path = first["Location"]
        form = self.dispatch(self.request("get", confirm_path, session=session))
        form.render()
        self.assertContains(form, "Elegí una contraseña nueva")
        changed = self.dispatch(self.request("post", confirm_path, {
            "new_password1": "A-New-Password-123!",
            "new_password2": "A-New-Password-123!",
        }, session=session))
        self.assertEqual(changed.status_code, 302)
        self.assertEqual(changed["Location"], reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("A-New-Password-123!"))

    @patch('django_recaptcha.client.submit', return_value=RecaptchaResponse(True, extra_data={'score': 0.9}, action='password_recovery'))
    def test_unknown_and_inactive_email_get_same_confirmation_without_mail(self, _captcha):
        reset_path = reverse("accounts:password_reset")
        unknown = self.dispatch(self.request("post", reset_path, {"email": "missing@example.test", "captcha": "valid-token"}))
        self.assertEqual(unknown["Location"], reverse("accounts:password_reset_done"))
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        inactive = self.dispatch(self.request("post", reset_path, {"email": self.user.email, "captcha": "valid-token"}))
        self.assertEqual(inactive["Location"], reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_allauth_paths_use_protected_hub_forms(self):
        self.assertIs(
            resolve('/accounts/login/', urlconf='passing.urls_public').func,
            resolve('/login/', urlconf='passing.urls_public').func,
        )
        response = self.dispatch(self.request('post', '/accounts/password/reset/', {
            'email': self.user.email,
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:password_reset'))
        self.assertEqual(len(mail.outbox), 0)

    def test_tenant_password_reset_redirects_to_protected_hub(self):
        path = '/login/reset-password/'
        match = resolve(path, urlconf='passing.urls_tenant')
        response = match.func(self.request('post', path, {'email': self.user.email}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('/accounts/recover/'))
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_captcha_blocks_login_and_recovery(self):
        login_form = HubLoginForm(data={"identity": self.user.email, "password": "old-password"})
        self.assertFalse(login_form.is_valid())
        self.assertIn("captcha", login_form.errors)

        response = self.dispatch(self.request("post", reverse("accounts:password_reset"), {
            "email": self.user.email,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    @patch('django_recaptcha.client.submit')
    def test_login_checks_recaptcha_action_and_score(self, submit):
        data = {"identity": self.user.email, "password": "old-password", "captcha": "token"}
        submit.return_value = RecaptchaResponse(True, extra_data={"score": 0.9}, action="hub_login")
        self.assertTrue(HubLoginForm(data=data).is_valid())

        submit.return_value = RecaptchaResponse(True, extra_data={"score": 0.9}, action="other_action")
        self.assertFalse(HubLoginForm(data=data).is_valid())
        submit.return_value = RecaptchaResponse(True, extra_data={"score": 0.1}, action="hub_login")
        self.assertFalse(HubLoginForm(data=data).is_valid())
        submit.side_effect = OSError("service unavailable")
        self.assertFalse(HubLoginForm(data=data).is_valid())
