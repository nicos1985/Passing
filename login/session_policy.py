"""Each login gets a fixed deadline, unaffected by later session writes."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone


@receiver(user_logged_in, dispatch_uid='passing.absolute_session_expiry')
def set_session_deadline(sender, request, user, **kwargs):
    request.session.set_expiry(
        timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE)
    )
