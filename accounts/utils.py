from django.core import signing
from django.utils import timezone
from django_tenants.utils import get_tenant_model
from client.models import Domain
from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings

TenantModel = get_tenant_model()

def build_oauth_state(client_slug: str, next_path: str = "/"):
    payload = {"client_slug": client_slug, "next": next_path, "ts": timezone.now().timestamp()}
    return signing.dumps(payload, salt="oauth-state-v1")

def build_sso_token(user_id: int, client_slug: str, next_path: str = "/",
                    salt: str = None):
    salt = salt or "sso-xfer-v1"
    payload = {"uid": user_id, "client_slug": client_slug, "next": next_path}
    return signing.dumps(payload, salt=salt)

def resolve_primary_domain(client: TenantModel) -> str:
    dom = Domain.objects.filter(tenant=client, is_primary=True).first()
    if not dom:
        return f"{client.schema_name}.localhost:8000"
    return dom.domain

def redirect_to_tenant_with_token(request, user, client, next_path="/"):
    client = TenantModel.objects.get(schema_name=str(client))  # aseguramos instancia fresh
    token = build_sso_token(
        user_id=user.id,
        client_slug=client.schema_name,
        next_path=next_path,
        salt=getattr(settings, "SSO_SIGNING_SALT", "sso-xfer-v1"),
    )

    domain = resolve_primary_domain(client)
    # En DEV, si el dominio no tiene punto, asumimos subdominio local
    host = domain if (not settings.DEBUG or "." in domain) else f"{domain}.localhost"
    scheme = "http" if settings.DEBUG else "https"
    port = _port_from_request(request) if settings.DEBUG else ""

    return redirect(f"{scheme}://{host}{port}/login/sso/consume/?token={token}")


def _port_from_request(request) -> str:
    """Devuelve ':<port>' si el hub viene con puerto (ej. :8000)."""
    host = request.get_host()
    if ":" in host:
        port = host.rsplit(":", 1)[-1]
        if port.isdigit():
            return f":{port}"
    return ""

def get_memberships_for_email(email: str):
    from .models import CustomUser, TenantMembership
    try:
        user = CustomUser.objects.get(email__iexact=email)
    except CustomUser.DoesNotExist:
        return None, TenantMembership.objects.none()
    mems = TenantMembership.objects.select_related("client").filter(user=user, is_active=True)
    return user, mems

def get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def get_ua(request):
    return request.META.get("HTTP_USER_AGENT", "")