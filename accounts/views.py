from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.conf import settings
from django.core import signing
from django.contrib.auth import get_user_model
from urllib3 import request
from urllib.parse import quote
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from client.models import Client, Domain
from .utils import build_oauth_state, build_sso_token
from django.contrib import messages, auth       
from allauth.account.utils import perform_login
from .utils import redirect_to_tenant_with_token, get_memberships_for_email
from .models import TenantMembership
from .forms import HubLoginForm

User = get_user_model()

import logging
logger = logging.getLogger(__name__)

DEFAULT_NEXT_PATH = "/login/home/"

def login_view(request):
    """
    Login tradicional en el hub (PUBLIC) con usuario/contraseña.
    Tras login exitoso -> branching por memberships (0/1/n).
    """
    next_path = request.GET.get("next") or DEFAULT_NEXT_PATH

    if request.method == "POST":
        form = HubLoginForm(request.POST)
        if form.is_valid():
            identity = form.cleaned_data["identity"]
            password = form.cleaned_data["password"]
            next_path = form.cleaned_data.get("next") or next_path

            user = authenticate(request, username=identity, password=password)
            if not user:
                messages.error(request, "Credenciales inválidas.")
                return render(request, "login.html", {"form": form, "next": next_path})

            auth_login(request, user)  # queda logueado en el hub
            return _branch_after_hub_login(request, user, next_path)
    else:
        form = HubLoginForm(initial={"next": next_path})

    return render(request, "login.html", {"form": form, "next": next_path})

def _branch_after_hub_login(request, user, next_path: str):
    """ Después de login en el hub, branching por memberships (0/1/n). """
    mems = (TenantMembership.objects
            .select_related("client")
            .filter(user=user, is_active=True))

    count = mems.count()
    if count == 0:
        messages.error(request, "Tu usuario no tiene cuentas asignadas. Contactá al administrador.")
        return redirect(reverse("login"))

    if count == 1:
        client = mems.first().client
        return redirect_to_tenant_with_token(request, user, client, next_path)

    # múltiples cuentas → selector
    request.session["tenant_select_next"] = next_path
    return redirect(reverse("choose_tenant_view"))


def logout_view(request):
    """ Cierra sesión en el hub y redirige a login. """
    auth_logout(request)
    messages.success(request, "Sesión cerrada.")
    return redirect(reverse("accounts:login"))


@login_required
def choose_tenant_view(request):
    """ Muestra un selector de tenants si el usuario tiene múltiples membresías.
    GET: muestra el formulario."""
    user = request.user
    next_path = request.session.get("tenant_select_next", DEFAULT_NEXT_PATH)
    mems = TenantMembership.objects.select_related("client")\
                                   .filter(user=user, is_active=True)\
                                   .order_by("client__name", "client__schema_name")
    if request.method == "POST":
        client_slug = request.POST.get("client_slug")
        m = mems.filter(client__schema_name=client_slug).first()
        if not m:
            messages.error(request, "No tenés acceso a esa cuenta.")
            return redirect(reverse("accounts:choose_tenant_view"))
        return redirect_to_tenant_with_token(request, request.user, m.client, next_path)

    # GET: mostrar selector de tenants
    return render(request, "choose_tenant.html", {
        "memberships": mems,
        "next": next_path,
    })



def google_start(request):
    """
    Initiates the Google OAuth login process.
    It expects 'client' and 'next' parameters in the GET request.
    """
    client_slug = request.GET.get("client")
    next_path = request.GET.get("next") or DEFAULT_NEXT_PATH
    logger.debug("google_start client_slug=%s next_path=%s", client_slug, next_path)
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
    """
    Después del login (Google vía allauth o credenciales del hub),
    si viene `_s` con client_slug => seguir tu flujo tradicional.
    Si NO viene client_slug => branching por memberships (0/1/n).
    """
    # --------- TU BLOQUE ORIGINAL (sin cambios) ---------
    state = request.GET.get("_s")
    logger.debug("post_login_redirect")
    # Debug statements removed to avoid verbose logs in production

    if not state:
        state = request.session.pop("oauth_state", None)

    client_slug = None
    next_path = DEFAULT_NEXT_PATH

    if state:
        try:
            logger.debug("state=%s", state)
            s = signing.loads(state, salt="oauth-state-v1", max_age=300)
            client_slug = s.get("client_slug")
            next_path = s.get("next") or DEFAULT_NEXT_PATH
        except signing.BadSignature:
            logger.warning("BadSignature while loading oauth state")
            pass

    if not client_slug:
        logger.debug("Fallback: client_slug no encontrado")
        client_slug = request.session.pop("oauth_client_slug", None)
    if next_path == "/":
        logger.debug("Fallback: next_path no encontrado")
        next_path = request.session.pop("oauth_next_path", DEFAULT_NEXT_PATH)
    # --------- FIN TU BLOQUE ORIGINAL ---------

    # 🔁 NUEVO: si NO hay client_slug, hacemos branching por memberships
    if not client_slug:
        user = request.user
        if not user.is_authenticated:
            messages.error(request, "No se pudo iniciar sesión.")
            return redirect(f"{reverse('login')}?next={next_path}")

        mems = TenantMembership.objects.select_related("client").filter(user=user, is_active=True)

        count = mems.count()
        if count == 0:
            messages.error(request, "Tu usuario no tiene cuentas asignados. Contactá al administrador.")
            return redirect(reverse("login"))

        if count == 1:
            client = mems.first().client

            logger.debug("client=%s type=%s", client, type(client))
            return redirect_to_tenant_with_token(request, user, mems.first().client, next_path)


        # múltiples cuentas → selector
        request.session["tenant_select_next"] = next_path
        return redirect(reverse("choose_tenant_view"))

    # Si SÍ hay client_slug (tu caso original) → seguimos como ya lo hacías
    dest = _resolve_tenant_base_url(request, client_slug)
    logger.debug("dest=%s", dest)
    token = build_sso_token(
        user_id=request.user.id,
        client_slug=client_slug,
        next_path=next_path,
        salt=getattr(settings, "SSO_SIGNING_SALT", "sso-xfer-v1"),
    )
    url = f"{dest}/login/sso/consume/?token={token}"
    # Return absolute redirect URL to tenant consume endpoint
    return redirect(url)

def google_start_auto(request):
    """
    Inicia Google OAuth SIN 'client'. Branching de tenants se hace en post_login_redirect.
    """
    next_path = request.GET.get("next") or DEFAULT_NEXT_PATH
    post_login_url = f"{reverse('post_login')}?next={quote(next_path)}"

    # Intentamos resolver la URL nombrada; si no existe, usamos el path de allauth.
    try:
        allauth_login_url = reverse("socialaccount_login", kwargs={"provider": "google"})
    except NoReverseMatch:
        # Path default que allauth expone al incluir 'allauth.urls' bajo /accounts/
        allauth_login_url = "/accounts/google/login/"

    return redirect(f"{allauth_login_url}?process=login&next={quote(post_login_url)}")

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