from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.core import signing
from django.contrib.auth import get_user_model
from urllib3 import request
from urllib.parse import quote

from client.models import Client, Domain
from .utils import build_oauth_state, build_sso_token

User = get_user_model()

def google_start(request):
    """
    Initiates the Google OAuth login process.
    It expects 'client' and 'next' parameters in the GET request.
    """
    client_slug = request.GET.get("client")
    next_path = request.GET.get("next") or "/"
    print(f'client_slug: {client_slug} / next_path: {next_path}')
    if not client_slug or not Client.objects.filter(schema_name=client_slug).exists():
        return HttpResponse("Client inválido.", status=400)

    # guardamos por duplicado: state y claves sueltas
    state = build_oauth_state(client_slug, next_path)
    request.session["oauth_state"] = state
    request.session["oauth_client_slug"] = client_slug
    request.session["oauth_next_path"] = next_path

    # allauth login para Google
    next_url = f"/accounts/post-login/?_s={quote(state)}"
    return redirect(f"/accounts/google/login/?process=login&next={quote(next_url)}")

@login_required
def post_login_redirect(request):
    """ After successful login, redirect to the appropriate tenant with SSO token.
    """
    # Plan B primero: viene por query
    state = request.GET.get("_s")
    # Plan A: si no vino por query, tomo de sesión

    print('post_login_redirect')
    # 1) tratamos de leer nuestro state
    if not state:
        state = request.session.pop("oauth_state", None)
    client_slug = None
    next_path = "/"

    if state:
        try:
            print(f'state: {state}')
            s = signing.loads(state, salt="oauth-state-v1", max_age=300)
            client_slug = s.get("client_slug")
            next_path = s.get("next") or "/"
        except signing.BadSignature:
            print("BadSignature")
            pass

    # 2) fallback por si se perdió el state
    if not client_slug:
        print("Fallback: client_slug no encontrado")
        client_slug = request.session.pop("oauth_client_slug", None)
    if next_path == "/":
        print("Fallback: next_path no encontrado")
        next_path = request.session.pop("oauth_next_path", "/")

    if not client_slug:
        
        # En última instancia, quedate en el hub
        return redirect("/")

    # 3) construir destino del tenant de manera robusta (soporta DEV con puerto)
    dest = _resolve_tenant_base_url(request, client_slug)
    print(f'dest: {dest}')
    token = build_sso_token(
        user_id=request.user.id,
        client_slug=client_slug,
        next_path=next_path,
        salt=getattr(settings, "SSO_SIGNING_SALT", "sso-xfer-v1"),
    )
    return redirect(f"{dest}/sso/consume/?token={token}")


def _resolve_tenant_base_url(request, client_slug: str) -> str:
    """
    Resolves the base URL for a given tenant, handling development and production environments.
    """
    scheme = "http" if settings.DEBUG else "https"
    base_dev = "localhost"  # puedes extraer a settings.TENANT_BASE_DOMAIN_DEV

    try:
        client = Client.objects.get(schema_name=client_slug)
    except Client.DoesNotExist:
        host = f"{client_slug}.{base_dev}" if settings.DEBUG else f"{client_slug}.passing.anima.bot"
        return f"{scheme}://{host}{_maybe_port(request)}"

    domain_obj = Domain.objects.filter(tenant=client).order_by("-is_primary").first()
    if domain_obj:
        host = domain_obj.domain
        # si en DEV el dominio no tiene ".", asumimos que es sólo el "schema"
        if settings.DEBUG and "." not in host:
            host = f"{host}.{base_dev}"
    else:
        host = f"{client_slug}.{base_dev}" if settings.DEBUG else f"{client_slug}.passing.anima.bot"

    return f"{scheme}://{host}{_maybe_port(request)}"

def _maybe_port(request):
    """ Adds port to the URL in development if present.
    """
    if settings.DEBUG:
        hub_host = request.get_host()
        if ":" in hub_host:
            _, _, port = hub_host.partition(":")
            if port.isdigit():
                return f":{port}"
    return ""