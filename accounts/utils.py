from django.core import signing
from django.utils import timezone

def build_oauth_state(client_slug: str, next_path: str = "/"):
    payload = {"client_slug": client_slug, "next": next_path, "ts": timezone.now().timestamp()}
    return signing.dumps(payload, salt="oauth-state-v1")

def build_sso_token(user_id: int, client_slug: str, next_path: str = "/",
                    salt: str = None):
    salt = salt or "sso-xfer-v1"
    payload = {"uid": user_id, "client_slug": client_slug, "next": next_path}
    return signing.dumps(payload, salt=salt)


def get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def get_ua(request):
    return request.META.get("HTTP_USER_AGENT", "")