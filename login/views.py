from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import SetPasswordForm
from client.models import Client
from permission.models import PermissionRoles
from .forms import CustomLoginForm, GlobalSettingsForm, UserRegisterForm, UserDepartureForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import CustomUser, GlobalSettings, MultifactorChoices
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, UpdateView, DetailView
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
import json
from django.utils.html import escape
import pyotp
import qrcode
from django.db import transaction
from urllib.parse import quote as urlquote
from io import BytesIO
from django.contrib.auth import login
from passing.config import EMAIL_SETTINGS
from django.core.mail import EmailMessage
from django.utils.html import format_html
from email.mime.image import MIMEImage
from django.contrib.auth import login, get_user_model
from django.core import signing
from django.http import HttpResponseForbidden
from django.conf import settings
from django_tenants.utils import get_tenant
from resources.models import Treatment, RiskEvaluation, TreatmentStage
from django.db.models import Count, Q
from threat_intel.models import IntelItem, Run, AIAnalysis
from django.db.models import Count
from accounts.models import TenantMembership, TenantSettings, AuthEvent
from accounts.utils import get_ip, get_ua
from django.contrib.auth import login as auth_login
from django.core.exceptions import PermissionDenied
from .utils import user_belongs_to_current_tenant
from .mixins import TenantScopedUserMixin
from .mixins import Safe404RedirectMixin

# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_superuser or user.is_staff

def is_superadmin(user):
    return user.is_superuser
#####################################

# Create your views here.
User = get_user_model()


def login_alias_to_home(request):
    """Alias 'login' -> home_tenant."""
    return redirect(reverse("home_tenant"))

def login_alias_to_hub(request):
    next_path = request.GET.get("next") or request.get_full_path()
    hub = getattr(settings, "HUB_ORIGIN", "http://localhost:8000").rstrip("/")
    return redirect(f"{hub}/accounts/?next={quote(next_path)}")

def home_tenant(request):
    # Dashboard data: treatment counts by stage and recent pending treatments
    stages_count = Treatment.objects.values('stage').annotate(count=Count('id'))
    # Build a mapping of stage -> count
    stage_counts = {item['stage']: item['count'] for item in stages_count}

    recent_pending = Treatment.objects.filter(stage=0).order_by('deadline')[:8]

    # Risk evaluations grouped by risk_level (0..4)
    risk_counts = (
        RiskEvaluation.objects.values('risk_level')
        .annotate(count=Count('id'))
    )
    # ensure we expose all levels (0..4)
    risk_map = {item['risk_level']: item['count'] for item in risk_counts}

    # Critical evaluations (high/very high)
    critical_evals = RiskEvaluation.objects.filter(risk_level__gte=3).select_related('evaluated_type')[:8]

    # Evaluations with treatments not implemented (treatment exists and treatment.stage != IMPLEMENTED)
    # Count evaluations that have an associated treatment and whose treatment
    # is NOT in IMPLEMENTED stage.
    evaluations_not_implemented = (
        RiskEvaluation.objects.filter(treatment__isnull=False)
        .exclude(treatment__stage=TreatmentStage.IMPLEMENTED)
        .count()
    )

    # Threat Intel: counts for the latest run (relevant items with AI analysis in that run)
    last_run = Run.objects.filter(status='success').order_by('-finished_at').first() or Run.objects.order_by('-started_at').first()
    ti_counts = {}
    recent_threats = []
    if last_run:
        # counts: all relevant items in last run (regardless of whether AIAnalysis exists)
        counts_qs = IntelItem.objects.filter(runitem__run=last_run, is_relevant=True).distinct()
        ti_counts_qs = counts_qs.values('severity').annotate(count=Count('id'))
        ti_counts = {item['severity']: item['count'] for item in ti_counts_qs}

        # recent list: keep items that also have an AIAnalysis in that run for richer context
        items_qs = IntelItem.objects.filter(runitem__run=last_run, is_relevant=True, aianalysis__run=last_run).distinct()
        recent_threats = items_qs.order_by('-runitem__detected_at')[:8]
    else:
        # fallback: any relevant items with AI analysis
        items_qs = IntelItem.objects.filter(is_relevant=True, aianalysis__isnull=False).distinct()
        ti_counts_qs = items_qs.values('severity').annotate(count=Count('id'))
        ti_counts = {item['severity']: item['count'] for item in ti_counts_qs}
        recent_threats = items_qs.order_by('-created_at')[:8]

    return render(request, 'home_tenant.html', {
        'stage_counts': stage_counts,
        'recent_pending': recent_pending,
        'risk_map': risk_map,
        'critical_evals': critical_evals,
        'evaluations_not_implemented': evaluations_not_implemented,
        'ti_counts': ti_counts,
        'recent_threats': recent_threats,
        'last_run_pk': last_run.pk if last_run else None,
    })


def register(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False
            
                username = form.cleaned_data['username']
                user.client = Client.objects.get(schema_name=request.tenant.schema_name)
                user.save()
            except Exception as e:
                messages.warning(request, 'La creacion de usuario ha tenido un problema save. error: {e}')

            try:
                # Generar token de activación
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))

                # Construir la URL de activación
                activation_url = f"http://{request.get_host()}/login/reset-password/confirm/{uid}/{token}/" #prestar atencion cuando pase a https
            except Exception as e:
                messages.warning(request, 'La creacion de usuario ha tenido un problema token. error: {e}')

            # Enviar correo electrónico
            subject = 'Activa tu cuenta de usuario'
            message = render_to_string('activation_email.html', {
                'user': user,
                'activation_url': activation_url,
            })

            try:
                send_mail(subject, message, 'noreply@anima.bot', [user.email])
            except Exception as e:
                messages.warning(request, f'No se ha podido enviar el mail a {user.email}')

            messages.success(request, f'El usuario {username} ha sido creado exitosamente')
            return redirect('userlist')
        else:
            messages.warning(request, 'La creacion de usuario ha tenido un problema.')

    else:
        form = UserForm()
        
    context = { 
        'form' : form,
        'title': 'Registrarse',
        'Action': 'create',
    }

    return render(request, 'register.html', context)

def create_uid_token(request):
    pass

def _hub_origin(request):
    # En settings: HUB_ORIGIN = "http://localhost:8000" (o tu dominio en prod)
    return getattr(settings, "HUB_ORIGIN", request.build_absolute_uri("/").rstrip("/"))



@transaction.atomic
def create_superuser(request, schema_name):
    """
    Crea el superuser inicial del tenant y su TenantMembership (activo).
    Envía mail de activación (usuario queda inactivo hasta activar).
    """
    client = get_object_or_404(Client, schema_name=schema_name)

    if getattr(client, "created_superuser", 0) == 1:
        messages.warning(request, "El usuario admin ya fue creado para este cliente.")
        return redirect("home")

    User = get_user_model()

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # 1) Crear usuario global (PUBLIC)
            user = form.save(commit=False)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = False  # hasta activar por email
            # ⚠️ NO hacer: user.client = client  (usuarios son globales)
            user.save()

            # 2) Crear/activar TenantMembership
            TenantMembership.objects.update_or_create(
                user=user, client=client, defaults={"is_active": True}
            )

            # 3) (Opcional) Crear TenantSettings si no existe
            TenantSettings.objects.get_or_create(client=client)

            # 4) Marcar bandera en el client (si fallara más abajo, la transacción revierte)
            if hasattr(client, "created_superuser"):
                client.created_superuser = 1
                client.save(update_fields=["created_superuser"])

            # 5) Enviar email de activación (link al HUB)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            hub = _hub_origin(request)  # p.ej. http://localhost:8000
            # asumamos que tenés un view en el HUB: accounts:activate
            # si todavía usás /login/activate/, ajustá el path abajo.
            try:
                activation_path = reverse("activate-superuser", kwargs={"uidb64": uid, "token": token})
            except Exception:
                activation_path = f"/login/activate/{uid}/{token}/"

            activation_url = f"{schema_name}.{hub}{activation_path}"
            subdom_url = f"{hub}/login/"

            subject = "Activa tu cuenta de usuario admin"
            message_html = render_to_string("activation_email.html", {
                "user": user,
                "activation_url": activation_url,
                "subdom_url": subdom_url
            })

            send_mail(subject, message="", from_email=settings.EMAIL_SETTINGS["DEFAULT_FROM_EMAIL"],
                      recipient_list=[user.email], html_message=message_html)

            messages.success(request, "El usuario admin ha sido creado. Revisa tu email para activarlo.")
            return render(request, "recive-mail.html", {
                "subject": subject,
                "message": message_html,  # si usás la vista que muestra el HTML
                "mail_from": settings.EMAIL_SETTINGS["DEFAULT_FROM_EMAIL"],
                "email": user.email,
                "action": "¿Recibiste el mail de verificación?"
            })
    else:
        form = UserRegisterForm()

    return render(request, "register.html", {
        "form": form,
        "title": "Crear usuario admin",
        "Action": "create",
    })


User = get_user_model()

def resend_mail(request):
    """Reenvia el mail en caso de que no lo haya recibido. Se dispara al presionar el boton de reenviar"""
    if request.method=='POST':
        subject = request.POST.get('subject')
        message_json = request.POST.get('message')
        mail_from = request.POST.get('mail_from')
        email = request.POST.get('email')
        action = request.POST.get('action')

        message_html = json.loads(message_json)
        context={'subject':subject,
                         'message': message_json,
                          'mail_from': mail_from,
                          'email': email,
                          'action': action}
        try:
            send_mail(subject, message='', from_email=mail_from, recipient_list=[email], html_message=message_html)
            
            messages.success(request, f'Se ha enviado el mail correctamente a {email}')
            context['action'] = '¿Recibiste el mail de verificacion?'
            return render(request,'recive-mail.html',context=context)
        
        except Exception as e:

            messages.error(request, f'Se ha producido un error al enviar el mail {e}')
            return render(request,'recive-mail.html',context=context) 
        
    return HttpResponse("Método no permitido", status=405)

def recive_mail(request):
    """Pregunta la recepcion de mail. En caso de no haberlo recibido da la opcion de reenviarlo."""
    if request.method=='GET':
        return render(request, 'recive-mail.html')


def activate_superuser(request, uidb64, token):
    """Activa el superuser cuando recibe el token correcto."""
    
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        
    
        current_schema = getattr(connection, "schema_name", None)
        client = Client.objects.filter(schema_name=current_schema).first()
            
        if client:
            TenantMembership.objects.update_or_create(
            user=user, client=client, defaults={"is_active": True}
            )
            client.created_superuser = 1
            client.save()
        messages.success(request, 'Tu cuenta ha sido activada exitosamente.')
        return redirect('home_tenant')

    else:
        messages.error(request, 'El enlace de activación es inválido o ha expirado.')
        return redirect('home')




class LogoutFormView(LogoutView):
    template_name = 'logout.html'

    def get_context_data(self, **kwargs):
          
          context = super().get_context_data(**kwargs)
          context['title'] = 'Logout'
          context['entity'] = 'Salida'
          context['list_url'] = reverse_lazy('login')
          context['action'] = 'logout'
            
          return context

        
@login_required
def profile_view(request):
    user = CustomUser.objects.get(id=request.user.id)
    if request.method == 'POST': 
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        if profile_form.is_valid():
            if profile_form.is_bound:
                is_2fa_enabled = profile_form.cleaned_data['is_2fa_enabled']
                if profile_form.initial['is_2fa_enabled'] == True:
                    if is_2fa_enabled == False:
                        disable_2fa(request)
                else:
                    qr_generate = is_2fa_enabled == True and user.otp_secret is None
                    if qr_generate:
                        profile_form.save()
                        return render(request, 'generate-qr-code.html')
                    else:
                        profile_form.save()
                        return render(request, 'listpass.html')
        else:
            print('Formulario no válido')
        
    else:
        profile_form = ProfileForm(instance=user)
        
        context = {
            'user_profile': user,
            'profile_form': profile_form,
            'has_otp_secret': user.has_otp_secret(),
        }
            
        return render(request, 'profile.html', context)
    return render(request, 'listpass.html')


class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = 'password_reset.html'
    success_message = "Se ha enviado un correo electrónico con instrucciones para restablecer la contraseña."


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'  # Cambia esto a la plantilla que estás utilizando
    form_class = SetPasswordForm  # Especifica el formulario que deseas utilizar

    def form_valid(self, form):
        # Guardar la nueva contraseña
        user = form.save()

        # Activar al usuario si no está activo
        if not user.is_active:
            
            user.is_active = True
            user.save()
            messages.success(self.request, "Tu cuenta ha sido activada con éxito.")

        # Llamar al comportamiento predeterminado del form_valid
        return super().form_valid(form)

@method_decorator(user_passes_test(is_administrator), name='dispatch') 
class UserListView(ListView):   
    model = CustomUser
    template_name = 'user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        obj = CustomUser.objects.filter(client=self.request.user.client).order_by('is_active')
        return obj
    
@method_decorator(user_passes_test(is_administrator), name='dispatch')
class UserUpdateView(Safe404RedirectMixin, TenantScopedUserMixin, UpdateView):
    model = CustomUser
    form_class = UserForm
    template_name = 'user_form.html'
    success_url = reverse_lazy('userlist')
    not_found_message = "No se encontró el usuario a editar."
    redirect_url_name = "userlist"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)  # puede lanzar Http404 → lo captura el mixin
        self.ensure_target_in_tenant(obj)   # si no pertenece al tenant, lanzá PermissionDenied
        return obj

    def get_initial(self):
        initial = super().get_initial()
        initial['birth_date'] = self.object.formatted_birth_date()
        initial['admission_date'] = self.object.formatted_admission_date()
        initial['departure_date'] = self.object.formatted_departure_date()
        return initial

@method_decorator(user_passes_test(is_administrator), name='dispatch')
class DepartureUser(Safe404RedirectMixin, TenantScopedUserMixin, UpdateView):
    model = CustomUser
    form_class = UserDepartureForm
    template_name = 'departure_user.html'
    success_url = reverse_lazy('userlist')
    not_found_message = "No se encontró el usuario a dar de baja."
    redirect_url_name = "userlist"


    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.ensure_target_in_tenant(obj)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.get_object()
        return context

    def form_valid(self, form):
        try:
            user = self.get_object()
            # Evitá autobaja del propio admin
            if user == self.request.user:
                messages.error(self.request, "No podés darte de baja a vos mismo.")
                return redirect('userlist')

            # Seguridad extra: revalida tenant
            if not user_belongs_to_current_tenant(user):
                raise PermissionDenied("No podés operar usuarios de otra cuenta.")

            deactivate = deactivate_user(self.request, user.id)
            messages.success(self.request, f"Se dió de baja exitosamente al usuario {user.username}.")
        except PermissionDenied as e:
            messages.error(self.request, str(e))
            return redirect('userlist')
        except Exception as e:
            messages.error(self.request, f"Error al dar de baja al usuario: {str(e)}")
        return super().form_valid(form)
 
@method_decorator(user_passes_test(is_administrator), name='dispatch')
class UserDetailView(Safe404RedirectMixin, TenantScopedUserMixin, DetailView):
    model = CustomUser
    template_name = 'detail-user.html'
    success_url = reverse_lazy('userlist')
    not_found_message = "No se encontró el usuario solicitado."
    redirect_url_name = "userlist"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.ensure_target_in_tenant(obj)
        return obj


@user_passes_test(is_administrator)
def deactivate_user(request, pk):
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        if not user_belongs_to_current_tenant(user):
            messages.error(request, "No podés operar usuarios de otro tenant.")
            return redirect('userlist')

        if user == request.user:
            messages.error(request, "No podés eliminar el mismo usuario con el que estás logueado.")
            return redirect('userlist')

        superusers = CustomUser.objects.filter(is_superuser=True, is_active=True).count()
        if user.is_superuser and superusers <= 1:
            messages.error(request, f'No se puede eliminar al usuario {user.username} ya que es el único administrador.')
            return redirect('userlist')

        message = user.inactivate()
        messages.success(request, message)
        return redirect('userlist')

    except Exception as e:
        messages.error(request, f"Error al desactivar el usuario: {str(e)}")
        return redirect('userlist')

@user_passes_test(is_administrator)
def activate_user(request, pk):
    try:
        user = get_object_or_404(CustomUser, id=pk)

        if not user_belongs_to_current_tenant(user):
            messages.error(request, "No podés operar usuarios de otra cuenta.")
            return redirect('userlist')

        message = user.activate()
        messages.success(request, message)
        return redirect('userlist')

    except Exception as e:
        messages.error(request, f"Error al activar el usuario: {str(e)}")
        return redirect('userlist')

def _resolve_2fa_user_from_request(request):
    """
    En flujo normal: devuelve request.user si está autenticado.
    En flujo SSO: usa la sesión (twofa_pending_uid) seteada en sso_consume.
    """
    if request.user.is_authenticated:
        return request.user

    pending_uid = request.session.get("twofa_pending_uid")
    client_id = request.session.get("twofa_client_id")
    if pending_uid and client_id:
        # opcional: podés chequear que connection.tenant.id == client_id
        return User.objects.filter(pk=pending_uid).first()

    return None


def verify_2fa(request):
    if request.method == "POST":
        code = request.POST.get("otp_code")
        if request.user.otp_secret:
            totp = pyotp.TOTP(request.user.otp_secret)
            if totp.verify(code):
                # Marcar como verificado en la sesión
                request.session["is_2fa_verified"] = True
                return redirect("listpass")  # Redirige al área protegida
            else:
                messages.error(request, "Código inválido. Intenta nuevamente.")
        else:
            messages.error(request, "2FA no está configurado en tu cuenta.")
    return render(request, "verify_2fa.html")


def show_qr_code_2fa(request):
    user_obj = _resolve_2fa_user_from_request(request)
    if not user_obj:
        return HttpResponseForbidden("Autenticación requerida o sesión SSO inválida.")

    if not getattr(user_obj, "otp_secret", None):
        user_obj.otp_secret = pyotp.random_base32()
        user_obj.is_2fa_enabled = False
        user_obj.save(update_fields=["otp_secret", "is_2fa_enabled"])

    # ... generás tu QR como ya lo hacías ...

    next_path = request.GET.get("next") or request.session.get("twofa_next") or "/"
    verify_url = reverse("verify_2fa_sso")  # /sso/verify-2fa/
    qr_b64 = generate_qr_base64(user_obj)  # o convertí tu bytes a base64
    context = {
        "qr_data_uri": f"data:image/png;base64,{qr_b64}",  # o usá qr_url si servís la imagen por URL
        "otp_secret": user_obj.otp_secret,                 # opcional (para clave manual)
        "next": request.GET.get("next") or request.session.get("twofa_next") or "/",
        "user_email": getattr(user_obj, "email", ""),
    }
    return render(request, "qr_2fa.html", context)

def generate_qr_bytes(user):
    """Genera un código QR en bytes para un usuario específico."""
    if not user.otp_secret:
        secret = user.otp_secret = pyotp.random_base32()  # Genera un secret si no lo tiene
        user.save()
    else:
        secret = user.otp_secret

    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        user.username,
        issuer_name="Passing"
    )

    qr = qrcode.make(totp_uri)  # Genera el código QR
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0) 

    return buffer  # Devuelve los bytes de la imagen

import base64

def generate_qr_base64(user):
    """Genera un código QR y lo devuelve como una cadena Base64."""
    qr_buffer = generate_qr_bytes(user)  # Reutilizamos la función anterior

    # Convertir la imagen a Base64
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')
    image_data = base64.b64decode(qr_base64)  # Decodificar Base64

    # Guardar la imagen en un archivo
    #with open("qr_code_test.png", "wb") as f:
        #f.write(image_data)
    return qr_base64  # Devuelve la cadena Base64

def disable_2fa(request):
    """
    Deshabilita el 2fa para el usuario en particular.
    """
    if request.method == "POST" and request.user.is_authenticated:
        request.user.is_2fa_enabled = False
        request.user.otp_secret = None
        request.user.save()
        messages.success(request, "2FA ha sido desactivado.")
    return redirect("profile")

def disable_2fa_user(user):
    """
    Deshabilita el 2fa para el usuario en particular.
    """
    user.is_2fa_enabled = False
    user.otp_secret = None
    user.save()
        
    


def send_qr_code_email_inline(user):
        """Envía el código QR incrustado en el cuerpo del email."""
        
        qr_base64 = generate_qr_base64(user)  # Obtener QR en Base64
        
        # Crear el cuerpo del email con la imagen incrustada
        html_content = format_html(
            """
            <html>
                <body>
                    <p>Hola <b>{}</b>,</p>
                    <p>Escanea este código QR para configurar la autenticación en dos pasos en la aplicación Passing:</p>
                    <p>Escanea el código QR con "Google Authenticator"  <a href="https://play.google.com/store/search?q=google+authenticator&c=apps&hl=es_419" target="_blank">Descargalo aqui</a></p>
                    <img src="data:image/png;base64,{}" alt="QR Code" style="width:200px; height:200px;">
                    <p>Si tienes problemas, contáctanos.</p>
                    <p>Atentamente, <br><b>El equipo de Passing</b></p>
                </body>
            </html>
            """,
            user.username, qr_base64
        )
        print(f'message_email {html_content}')
        # Crear el email con formato HTML
        email = EmailMessage(
            subject="Tu Código QR para Autenticación en Passing",
            body=html_content,
            from_email="noreply@anima.bot",
            to=[user.email]
        )

        email.content_subtype = "html"  # Especificar que el contenido es HTML

        # Enviar el email
        email.send()

def send_qr_code_email_cid(user):
    """Envía el código QR como imagen embebida en el correo (CID)."""
    qr_buffer = generate_qr_bytes(user)  # Genera la imagen en bytes

    # Crear el email con HTML y referenciar la imagen con CID
    subject = "Tu Código QR para Autenticación en Passing"
    message = """
    <html>
        <body>
            <p>Hola <b>{}</b>,</p>
            <p>Escanea este código QR para configurar la autenticación en dos pasos en la aplicación Passing:</p>
            <p>Escanea el código QR con "Google Authenticator"  <a href="https://play.google.com/store/search?q=google+authenticator&c=apps&hl=es_419" target="_blank">Descargalo aqui</a></p>
            <img src="cid:qrcode" alt="QR Code" style="width:200px; height:200px;">
            <p>Si tienes problemas, contáctanos.</p>
            <p>Atentamente, <br><b>El equipo de Passing</b></p>
        </body>
    </html>
    """.format(user.username)

    email = EmailMessage(subject, message, 'noreply@anima.bot', [user.email])
    email.content_subtype = "html"  # Importante para permitir HTML en el email

    # Crear la imagen como un archivo adjunto embebido
    image = MIMEImage(qr_buffer.getvalue(), _subtype="png")
    image.add_header('Content-ID', '<qrcode>')  # CID que se usa en el <img>
    image.add_header('Content-Disposition', 'inline', filename="qrcode.png")
    email.attach(image)  # Adjuntar la imagen al email

    email.send()
    
def send_qr_email_for_user_ondemand(request, pk):
    user = CustomUser.objects.get(id=pk)
    try:
        send_qr_code_email_cid(user)
        messages.success(request, f"El código QR a {user} se ha enviado correctamente al correo {user.email}.")
    except Exception as e:
        messages.warning(request, f'El mail no ha podido enviarse a {user.email}. ERROR: {e}')

    return redirect('userlist')


class GlobalSettingsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista para update las configuraciones globales a nivel de cuenta.
    """
    model = GlobalSettings
    template_name = 'global_settings.html'
    form_class = GlobalSettingsForm
    success_url = reverse_lazy('config')

    def test_func(self):
        return is_administrator(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a Configuraciones Globales")
        return redirect('listpass')  # Redirigir a la página de inicio u otra página adecuada

    def get_queryset(self):
        
        return super().get_queryset()
    
    
    
    def form_valid(self, form):
        """Intercepta la validación antes de guardar"""
        instance = form.save(commit=False)  # Obtiene el objeto sin guardarlo aún

        if instance.multifactor_status == MultifactorChoices.ACTIVADO:
            # Ejecuta una función si el campo `multifactor_status` está activado
            print(f'pasa por activado')
            self.activate_multifactor_for_all()
        elif instance.multifactor_status == MultifactorChoices.DESACTIVADO:
            print(f'pasa por desactivado')
            self.deactivate_multifactor_for_all()

        instance.save()  # Guarda el objeto en la base de datos
        form.save_m2m()  # Guarda las relaciones ManyToMany si existen

        return super().form_valid(form)
    

    def activate_multifactor_for_all(self):
        """
        Activa todos los factores multiples de autenticacion a todos los usuarios. 
        Envia mail a cada uno con el QR para la activacion del mismo. 
        """
        users = CustomUser.objects.filter(is_active=True)
        

        for user in users:
            
            if user.is_2fa_enabled:
                pass
            else:
                user.is_2fa_enabled = True
                user.save()
                send_qr_code_email_cid(user)


    def deactivate_multifactor_for_all(self):
        """desactiva todos los factores multiples de autenticacion a todos los usuarios."""
        users = CustomUser.objects.filter(is_active=True)
        
        for user in users:
            if user.has_otp_secret:
                disable_2fa_user(user)

from django.db import connection
def sso_consume(request):
    print("DEBUG schema_name en request:", getattr(connection, "schema_name", None))
    token = request.GET.get("token")
    if not token:
        return HttpResponseForbidden("Token requerido.")

    try:
        payload = signing.loads(
            token,
            salt=getattr(settings, "SSO_SIGNING_SALT", "sso-xfer-v1"),
            max_age=getattr(settings, "SSO_TRANSFER_TTL_SECONDS", 90),
        )
    except signing.BadSignature:
        return HttpResponseForbidden("Token inválido o vencido.")

    uid = payload.get("uid")
    next_path = payload.get("next") or "/"
    slug = payload.get("client_slug")

    user = User.objects.filter(pk=uid).first()
    if not user or not user.is_active:
        return HttpResponseForbidden("Usuario inválido.")

    # 1) Intento por middleware
    tenant = get_tenant(request)

    # 2) Fallback por slug (robusto si tenant viene None o no coincide)
    client = None
    if tenant is not None and getattr(tenant, "schema_name", None) == slug:
        client = tenant
    else:
        client = Client.objects.filter(schema_name=slug).first()

    if not client:
        return HttpResponseForbidden("Tenant desconocido.")

    # 3) Chequeo de membresía en PUBLIC
    has_membership = TenantMembership.objects.filter(
        user_id=user.id, client_id=client.id, is_active=True
    ).exists()
    if not has_membership:
        return HttpResponseForbidden("No tienes acceso a este espacio.")

    # 4) Gate 2FA (si lo estás usando)
    ts = getattr(client, "settings", None)
    require_2fa = bool(ts and ts.sso_google_requires_2fa)

    if require_2fa:
        # seteo de sesión para el flujo SSO 2FA
        request.session["twofa_pending_uid"] = user.id
        request.session["twofa_next"] = next_path
        request.session["twofa_client_id"] = client.id
        # SIEMPRE vamos a la vista SSO de verificación (ella decide enrolar o verificar)
        return redirect(reverse("verify_2fa_sso"))

    # 5) Login y listo
    _login_with_backend(request, user)
    return redirect(next_path)

def _login_with_backend(request, user):
    backend = None
    # Permití sobreescribir por settings si querés
    backend = getattr(settings, "SSO_LOGIN_BACKEND", None)
    if not backend:
        # Usa el primero configurado o ModelBackend por defecto
        backend = settings.AUTHENTICATION_BACKENDS[0] if getattr(settings, "AUTHENTICATION_BACKENDS", None) else "django.contrib.auth.backends.ModelBackend"
    auth_login(request, user, backend=backend)



def verify_2fa_sso(request):
    uid = request.session.get("twofa_pending_uid")
    next_path = request.GET.get("next") or request.POST.get("next") \
                or request.session.get("twofa_next") or "/"
    client_id = request.session.get("twofa_client_id")

    if not uid or not client_id:
        return HttpResponseForbidden("Sesión de 2FA inválida.")

    user = User.objects.filter(pk=uid).first()
    if not user:
        return HttpResponseForbidden("Usuario no válido.")

    # --- GET: mostrar form si YA HAY otp_secret; si falta => ir a QR ---
    if request.method == "GET":
        if not user.otp_secret:  # <- SOLO este caso va a enrolamiento
            enrol_url = reverse("show-qr-code-2fa")
            return redirect(f"{enrol_url}?next={urlquote(next_path)}&sso=1&uid={user.id}")

        # Mostrar el form de verificación (podés reutilizar qr_2fa.html o tener un template aparte)
        return render(request, "qr_2fa.html", {
            "next": next_path,
            "user_email": user.email,
            # Opcional: no mandes QR aquí para que el usuario se concentre en ingresar el código
            # Si querés mostrarlo igual, pasá qr_data_uri como en show_qr_code_2fa
        })

    # --- POST: validar el TOTP SIEMPRE; NO redirigir a QR aquí ---
    code = (request.POST.get("code") or "").strip()

    if not user.otp_secret:
        # Aún no enrolado (escenario raro si llegaste por POST)
        enrol_url = reverse("show-qr-code-2fa")
        return redirect(f"{enrol_url}?next={urlquote(next_path)}&sso=1&uid={user.id}")

    ok = False
    try:
        totp = pyotp.TOTP(user.otp_secret)
        ok = totp.verify(code, valid_window=1)
    except Exception:
        ok = False

    if ok:
        if not user.is_2fa_enabled:
            user.is_2fa_enabled = True
            user.save(update_fields=["is_2fa_enabled"])

        # limpiar sesión sso-2fa
        for k in ("twofa_pending_uid", "twofa_next", "twofa_client_id"):
            request.session.pop(k, None)

        _login_with_backend(request, user)
        return redirect(next_path)

    # Código inválido: re-render con error (sin mandar a QR)
    return render(request, "qr_2fa.html", {
        "otp_secret": user.otp_secret,
        "error": "Código inválido o expirado. Probá nuevamente.",
        "next": next_path,
        "user_email": user.email,
    }, status=403)