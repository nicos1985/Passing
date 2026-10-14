from django.contrib.auth.decorators import login_required
from django.utils import translation
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import SetPasswordForm
from client.models import Client
from permission.models import PermissionRoles
from .forms import CustomLoginForm, TenantSettingsForm, UserRegisterForm, UserDepartureForm, ProfileForm, UserForm
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.models import CustomUser, MultiFactorStatus
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, UpdateView, DetailView
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
import json
from smtplib import SMTPAuthenticationError, SMTPConnectError, SMTPRecipientsRefused, SMTPSenderRefused, SMTPServerDisconnected
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
import logging

logger = logging.getLogger(__name__)
from resources.models import Treatment, RiskEvaluation, TreatmentStage, VendorEvaluation, VendorEvaluationStatus
from django.db.models import Count, Q
from threat_intel.models import IntelItem, Run, AIAnalysis
from django.db.models import Count
from accounts.models import TenantMembership, TenantSettings, AuthEvent
from accounts.utils import get_ip, get_ua
from django.contrib.auth import login as auth_login
from django.core.exceptions import PermissionDenied
from .utils import user_belongs_to_current_tenant, users_for_current_tenant
from .mixins import TenantScopedUserMixin
from .mixins import Safe404RedirectMixin
import logging
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

# Funcion para user_passes_test 
def is_administrator(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff) and user_belongs_to_current_tenant(user)

def is_superadmin(user):
    return user.is_superuser
#####################################

# Create your views here.
User = get_user_model()

PENDING_EVALUATION_WINDOW_DAYS = 14

def _pending_vendor_evaluations_for_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_vendorevaluation')):
        return VendorEvaluation.objects.none()
    include_all = request.user.is_staff or request.user.is_superuser
    today = timezone.localdate()
    end_date = today + timedelta(days=PENDING_EVALUATION_WINDOW_DAYS)
    qs = (
        VendorEvaluation.objects.filter(
            status=VendorEvaluationStatus.PENDING,
            scheduled_date__isnull=False,
            scheduled_date__lte=end_date,
        )
        .select_related('vendor')
        .order_by('scheduled_date')
    )
    if include_all:
        return qs
    return qs.filter(vendor__owner=request.user)


def login_alias_to_home(request):
    """Alias 'login' -> home_tenant."""
    return redirect(reverse("home_tenant"))

def login_alias_to_hub(request):
    next_path = request.GET.get("next") or request.get_full_path()
    hub = getattr(settings, "HUB_ORIGIN", "http://localhost:8000").rstrip("/")
    return redirect(f"{hub}/accounts/?next={quote(next_path)}")

@login_required
def home_tenant(request):
    """Dashboard tenant con métricas de treatments, riesgos y threat intelligence recientes."""
    can_view_treatments = request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_treatment')
    can_view_risks = request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_riskevaluation')
    can_view_vendor_evaluations = request.user.is_staff or request.user.is_superuser or request.user.has_perm('resources.view_vendorevaluation')
    # Dashboard data: treatment counts by stage and recent pending treatments
    stages_count = Treatment.objects.values('stage').annotate(count=Count('id')) if can_view_treatments else []
    # Build a mapping of stage -> count
    stage_counts = {item['stage']: item['count'] for item in stages_count}

    recent_pending = Treatment.objects.filter(stage=0).order_by('deadline')[:8] if can_view_treatments else []

    # Risk evaluations grouped by risk_level (0..4)
    risk_counts = (
        RiskEvaluation.objects.filter(is_draft=False).values('risk_level')
        .annotate(count=Count('id'))
    ) if can_view_risks else []
    # ensure we expose all levels (0..4)
    risk_map = {item['risk_level']: item['count'] for item in risk_counts}

    # Critical evaluations (high/very high)
    critical_evals = RiskEvaluation.objects.filter(is_draft=False, risk_level__gte=3).select_related('evaluated_type')[:8] if can_view_risks else []

    # Evaluations with treatments not implemented (treatment exists and treatment.stage != IMPLEMENTED)
    # Count evaluations that have an associated treatment and whose treatment
    # is NOT in IMPLEMENTED stage.
    evaluations_not_implemented = (
        RiskEvaluation.objects.filter(is_draft=False, treatment__isnull=False)
        .exclude(treatment__stage=TreatmentStage.IMPLEMENTED)
        .count()
    ) if can_view_risks else 0

    # Threat Intel: counts for the latest run (relevant items with AI analysis in that run)
    can_view_threat_intel = request.user.is_superuser or all(
        request.user.has_perm(f'threat_intel.view_{model}')
        for model in ('run', 'runitem', 'intelitem', 'aianalysis', 'report')
    )
    last_run = (
        Run.objects.filter(status='success').order_by('-finished_at').first()
        or Run.objects.order_by('-started_at').first()
    ) if can_view_threat_intel else None
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
    elif can_view_threat_intel:
        # fallback: any relevant items with AI analysis
        items_qs = IntelItem.objects.filter(is_relevant=True, aianalysis__isnull=False).distinct()
        ti_counts_qs = items_qs.values('severity').annotate(count=Count('id'))
        ti_counts = {item['severity']: item['count'] for item in ti_counts_qs}
        recent_threats = items_qs.order_by('-created_at')[:8]

    pending_eval_qs = _pending_vendor_evaluations_for_dashboard(request)
    pending_evals_card_count = pending_eval_qs.count()
    pending_evals_card_list = list(pending_eval_qs[:3])

    return render(request, 'home_tenant.html', {
        'stage_counts': stage_counts,
        'can_view_treatments': can_view_treatments,
        'can_view_risks': can_view_risks,
        'recent_pending': recent_pending,
        'risk_map': risk_map,
        'critical_evals': critical_evals,
        'evaluations_not_implemented': evaluations_not_implemented,
        'ti_counts': ti_counts,
        'recent_threats': recent_threats,
        'last_run_pk': last_run.pk if last_run else None,
        'can_view_threat_intel': can_view_threat_intel,
        'pending_evals_card_count': pending_evals_card_count,
        'can_view_vendor_evaluations': can_view_vendor_evaluations,
        'pending_evals_card_list': pending_evals_card_list,
        'pending_evals_window_days': PENDING_EVALUATION_WINDOW_DAYS,
    })


class ActivationEmailNotAccepted(Exception):
    """El backend no aceptó ningún mensaje, aunque no haya lanzado una excepción."""


def _activation_mail_failure_message(exc):
    if isinstance(exc, SMTPAuthenticationError):
        return 'El servidor SMTP rechazó las credenciales. Revisá el usuario y la contraseña de correo.'
    if isinstance(exc, (SMTPConnectError, SMTPServerDisconnected, TimeoutError, ConnectionError, OSError)):
        return 'No se pudo conectar al servidor SMTP. Revisá el host, puerto, TLS y las reglas de red.'
    if isinstance(exc, SMTPSenderRefused):
        return 'El servidor SMTP rechazó el remitente configurado.'
    if isinstance(exc, SMTPRecipientsRefused):
        return 'El servidor SMTP rechazó la dirección del destinatario.'
    return 'El servidor de correo no aceptó la invitación. Revisá la configuración SMTP.'


def _send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_url = request.build_absolute_uri(
        reverse('password_reset_confirm', args=[uid, token])
    )
    accepted = send_mail(
        'Activa tu cuenta de usuario',
        render_to_string('activation_email.html', {'user': user, 'activation_url': activation_url}),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    if accepted != 1:
        raise ActivationEmailNotAccepted()


def _log_activation_mail_failure(user, exc):
    logger.warning(
        'No se pudo enviar la activación del usuario %s: %s (SMTP %s)',
        user.pk, type(exc).__name__, getattr(exc, 'smtp_code', '-'),
    )


@user_passes_test(is_administrator)
def register(request):
    """Crea un usuario inactivo y su membresía en una única transacción."""
    form = UserForm(request.POST or None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                user.client = get_tenant(request)
                user.is_active = False
                user.is_superuser = False  # Los superusuarios se crean por consola.
                user.set_unusable_password()
                user.save()
                TenantMembership.objects.create(user=user, client=user.client, is_active=True)
        except Exception:
            logger.exception('No se pudo crear el usuario en el tenant actual')
            form.add_error(None, 'No se pudo crear el usuario. Revisá los datos e intentá nuevamente.')
        else:
            try:
                _send_activation_email(request, user)
            except Exception as exc:
                _log_activation_mail_failure(user, exc)
                messages.warning(request, 'El usuario se creó, pero no llegó a enviarse la invitación. ' + _activation_mail_failure_message(exc))
            messages.success(request, f'El usuario {user.username} se creó en este tenant y está pendiente de activación.')
            return redirect('userlist')

    return render(request, 'register.html', {'form': form, 'title': 'Crear usuario'})


@user_passes_test(is_administrator)
@require_POST
def resend_activation(request, pk):
    user = get_object_or_404(users_for_current_tenant(), pk=pk, is_active=False)
    if user.password and user.has_usable_password():
        messages.warning(request, 'Este usuario ya tiene contraseña. Usá la opción de activación de la lista.')
        return redirect('userlist')
    try:
        _send_activation_email(request, user)
    except Exception as exc:
        _log_activation_mail_failure(user, exc)
        messages.error(request, _activation_mail_failure_message(exc))
    else:
        messages.success(request, f'El servidor de correo aceptó la invitación para {user.email}.')
    return redirect('userlist')

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
        user = get_object_or_404(CustomUser.for_current_tenant(), pk=uid)
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

    def get(self, request, *args, **kwargs):
        # Opcional: Renderiza el formulario de confirmación para GET
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        # Maneja la solicitud POST para cerrar sesión
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Logout'
        context['entity'] = 'Salida'
        context['list_url'] = reverse_lazy('login')
        context['action'] = 'logout'
        return context
        
@login_required
def profile_view(request):
    """Actualiza datos del perfil y el avatar del usuario autenticado, incluyendo 2FA."""
    user = CustomUser.objects.get(id=request.user.id)
    if request.method == 'POST': 
        logger = logging.getLogger(__name__)
        logger.debug("profile_view POST: files=%s", list(request.FILES.keys()))
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        logger.debug("profile_form bound=%s", profile_form.is_bound)
        valid = profile_form.is_valid()
        logger.debug("profile_form is_valid=%s errors=%s", valid, profile_form.errors.as_json() if profile_form.errors else None)
        if valid and profile_form.is_bound:
            is_2fa_enabled = profile_form.cleaned_data.get('is_2fa_enabled')
            initial_2fa = profile_form.initial.get('is_2fa_enabled')
            policy = TenantSettings.for_client(get_tenant(request))
            if policy and policy.multifactor_status == MultiFactorStatus.REQUIRED:
                profile_form.instance.is_2fa_enabled = True
                is_2fa_enabled = True
            # Determine whether we need to show QR after saving (newly enabled 2FA)
            qr_generate = initial_2fa != True and is_2fa_enabled == True and user.otp_secret is None

            try:
                profile_form.save()
                if initial_2fa is True and is_2fa_enabled is False:
                    disable_2fa(request)
                user.refresh_from_db()
                logger.debug("After save: user.avatar.name=%s", getattr(user.avatar, 'name', None))
                messages.success(request, "Perfil actualizado correctamente.")


                # Aplicar preferencia de idioma guardada en el perfil del usuario
                new_lang = profile_form.cleaned_data.get('language')
                if new_lang:
                    session_key = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
                    request.session[session_key] = new_lang
                    translation.activate(new_lang)

                # Mantener al usuario en su perfil para revisar los cambios.
                if qr_generate:
                    response = render(request, 'generate-qr-code.html')
                else:
                    response = redirect('profile')

                try:
                    response.set_cookie(getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language'), new_lang or '')
                except Exception:
                    pass

                return response

            except Exception as exc:
                logger.exception("Error saving profile form/avatar: %s", exc)
                messages.error(request, 'No se pudieron guardar los cambios del perfil.')
        else:
            logger.warning("Profile form invalid: %s", profile_form.errors)
            messages.error(request, 'Revisá los campos marcados para guardar el perfil.')
        
    else:
        profile_form = ProfileForm(instance=user)
        
    from supporthub.models import TelegramRecipient
    context = {
        'user_profile': user,
        'profile_form': profile_form,
        'has_otp_secret': user.has_otp_secret(),
        'mfa_required': getattr(TenantSettings.for_client(get_tenant(request)), 'multifactor_status', None) == MultiFactorStatus.REQUIRED,
        'telegram_recipient': TelegramRecipient.objects.filter(user=user).first(),
        'can_monitor_alerts': user.is_superuser or user.has_perm('monitoring.manage_monitoring') or user.has_perm('monitoring.read_monitoring'),
    }
    return render(request, 'profile.html', context)


class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    """LoginView derivado que muestra la plantilla propia del hub para resetear contraseña."""
    template_name = 'password_reset.html'
    success_message = "Se ha enviado un correo electrónico con instrucciones para restablecer la contraseña."


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Confirma el token y activa al usuario cuando recupera la contraseña."""
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
    """Lista los usuarios del tenant para administradores."""
    model = CustomUser
    template_name = 'user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return users_for_current_tenant().order_by('-is_active', 'username')
    
@method_decorator(user_passes_test(is_administrator), name='dispatch')
class UserUpdateView(Safe404RedirectMixin, TenantScopedUserMixin, UpdateView):
    """Actualiza los datos de un usuario, garantizando que pertenezca al tenant."""
    model = CustomUser
    form_class = UserForm
    template_name = 'user_form.html'
    success_url = reverse_lazy('userlist')
    not_found_message = "No se encontró el usuario a editar."
    redirect_url_name = "userlist"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_staff=False, is_superuser=False)
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs

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
    """Maneja la desactivación ordenada de un usuario dentro del tenant."""
    model = CustomUser
    form_class = UserDepartureForm
    template_name = 'departure_user.html'
    success_url = reverse_lazy('userlist')
    not_found_message = "No se encontró el usuario a dar de baja."
    redirect_url_name = "userlist"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_staff=False, is_superuser=False)
        return queryset

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.ensure_target_in_tenant(obj)
        return obj

    def get_context_data(self, **kwargs):
        """Incluye el usuario objetivo en el contexto del formulario de baja."""
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
    """Expone la información de un usuario dentro del tenant con seguridad."""
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
    """Inactiva un usuario asegurando que no sea el único superusuario activo."""
    try:
        user = get_object_or_404(users_for_current_tenant(), pk=pk)
        if not request.user.is_superuser and (user.is_staff or user.is_superuser):
            raise PermissionDenied('No podés desactivar administradores.')

        if not user_belongs_to_current_tenant(user):
            messages.error(request, "No podés operar usuarios de otro tenant.")
            return redirect('userlist')

        if user == request.user:
            messages.error(request, "No podés eliminar el mismo usuario con el que estás logueado.")
            return redirect('userlist')

        superusers = users_for_current_tenant().filter(is_superuser=True, is_active=True).count()
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
@require_POST
def activate_user(request, pk):
    """Re-activa un usuario previamente desactivado y registra el mensaje de éxito."""
    try:
        user = get_object_or_404(users_for_current_tenant(), id=pk)
        if not request.user.is_superuser and (user.is_staff or user.is_superuser):
            raise PermissionDenied('No podés activar administradores.')
        if not user.password or not user.has_usable_password():
            messages.warning(request, 'El usuario todavía debe definir su contraseña. Reenviá la invitación.')
            return redirect('userlist')

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
        tenant = get_tenant(request)
        if tenant and tenant.id == client_id:
            return User.objects.filter(pk=pending_uid, is_active=True).first()

    return None


def verify_2fa(request):
    """Verifica el código TOTP del usuario enrutado por el middleware 2FA."""
    if not request.user.is_authenticated:
        return HttpResponseForbidden('Autenticación requerida.')
    if not request.user.otp_secret:
        return redirect('show-qr-code-2fa')
    if request.method == "POST":
        code = request.POST.get("otp_code")
        if request.user.otp_secret:
            totp = pyotp.TOTP(request.user.otp_secret)
            if totp.verify(code, valid_window=1):
                # Marcar como verificado en la sesión
                request.session["is_2fa_verified"] = True
                tenant = get_tenant(request)
                request.session['twofa_verified_user_id'] = request.user.pk
                request.session['twofa_verified_client_id'] = tenant.pk
                policy = TenantSettings.for_client(tenant)
                if policy and policy.multifactor_status == MultiFactorStatus.REQUIRED and not request.user.is_2fa_enabled:
                    request.user.is_2fa_enabled = True
                    request.user.save(update_fields=['is_2fa_enabled'])
                return redirect("listpass")  # Redirige al área protegida
            else:
                messages.error(request, "Código inválido. Intenta nuevamente.")
        else:
            messages.error(request, "2FA no está configurado en tu cuenta.")
    return render(request, "verify_2fa.html")


def show_qr_code_2fa(request):
    """Muestra el QR generado para enrolar el segundo factor."""
    user_obj = _resolve_2fa_user_from_request(request)
    if not user_obj:
        return HttpResponseForbidden("Autenticación requerida o sesión SSO inválida.")

    if not getattr(user_obj, "otp_secret", None):
        user_obj.otp_secret = pyotp.random_base32()
        user_obj.save(update_fields=["otp_secret"])

    # ... generás tu QR como ya lo hacías ...

    next_path = request.GET.get("next") or request.session.get("twofa_next") or "/"
    is_sso = not request.user.is_authenticated
    qr_b64 = generate_qr_base64(user_obj)  # o convertí tu bytes a base64
    context = {
        "qr_data_uri": f"data:image/png;base64,{qr_b64}",  # o usá qr_url si servís la imagen por URL
        "next": request.GET.get("next") or request.session.get("twofa_next") or "/",
        "user_email": getattr(user_obj, "email", ""),
        "verify_url": reverse('verify_2fa_sso' if is_sso else 'verify_2fa'),
        "code_field": 'code' if is_sso else 'otp_code',
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
        policy = TenantSettings.for_client(get_tenant(request))
        if policy and policy.multifactor_status == MultiFactorStatus.REQUIRED:
            return HttpResponseForbidden('El segundo factor es obligatorio en este espacio.')
        request.user.is_2fa_enabled = False
        request.user.otp_secret = None
        request.user.save()
        messages.success(request, "2FA ha sido desactivado.")
    return redirect("profile")

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
    logger.debug('Prepared QR email for user %s (HTML content omitted)', user.username)
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
    
@user_passes_test(is_administrator)
@require_POST
def send_qr_email_for_user_ondemand(request, pk):
    """Envía el QR por email cuando el admin lo solicita explícitamente."""
    user = get_object_or_404(users_for_current_tenant(), id=pk)
    if not request.user.is_superuser and (user.is_staff or user.is_superuser):
        return HttpResponseForbidden('No podés enviar el QR de un administrador.')
    try:
        send_qr_code_email_cid(user)
        messages.success(request, f"El código QR a {user} se ha enviado correctamente al correo {user.email}.")
    except Exception as e:
        messages.warning(request, f'El mail no ha podido enviarse a {user.email}. ERROR: {e}')

    return redirect('userlist')


class TenantSettingsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vista para editar `TenantSettings` por cliente (reemplaza GlobalSettings)."""
    model = TenantSettings
    template_name = 'global_settings.html'
    form_class = TenantSettingsForm
    success_url = reverse_lazy('config')

    def test_func(self):
        return is_superadmin(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a Configuraciones Globales")
        return redirect('listpass')

    def get_object(self):
        # Retornar o crear el TenantSettings asociado al cliente/tenant actual
        try:
            tenant = get_tenant(self.request)
            client = tenant
        except Exception:
            client = getattr(self.request.user, 'client', None)

        obj = TenantSettings.for_client(client)
        if obj is None and client is not None:
            obj = TenantSettings.objects.create(client=client)
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pass request so the form can scope `set_admins` to tenant users
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import os
        from supporthub.forms import BotTokenForm
        from supporthub.models import TelegramBotConfig, TelegramRecipient

        bot = TelegramBotConfig.objects.filter(pk=1).first()
        context['telegram_bot_source'] = ('passing' if bot and bot.token_encrypted else
                                          'environment' if os.getenv('SUPPORT_TELEGRAM_BOT_TOKEN', '').strip() else None)
        context['telegram_bot_form'] = BotTokenForm()
        context['telegram_recipients'] = TelegramRecipient.objects.select_related('user').all()
        context['telegram_discovered_chats'] = self.request.session.pop('telegram_discovered_chats', None)
        return context

    def form_valid(self, form):
        instance = form.save(commit=False)

        instance.save()
        form.save_m2m()
        self.object = instance
        return redirect(self.get_success_url())
    

from django.db import connection
def sso_consume(request):
    """Consume el token SSO, valida membresía y completa el login sin hacer form manual."""
    # debug removed: do not log request headers in production
    # print("DEBUG schema_name en request:", getattr(connection, "schema_name", None))
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
    if not url_has_allowed_host_and_scheme(next_path, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_path = '/'
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
    require_2fa = bool(ts and (
        ts.sso_google_requires_2fa
        or ts.multifactor_status == MultiFactorStatus.REQUIRED
        or (ts.multifactor_status == MultiFactorStatus.OPTIONAL and user.is_2fa_enabled)
    ))

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
    """Ejecuta el login forzado usando el backend configurado para SSO."""
    backend = None
    # Permití sobreescribir por settings si querés
    backend = getattr(settings, "SSO_LOGIN_BACKEND", None)
    if not backend:
        # Usa el primero configurado o ModelBackend por defecto
        backend = settings.AUTHENTICATION_BACKENDS[0] if getattr(settings, "AUTHENTICATION_BACKENDS", None) else "django.contrib.auth.backends.ModelBackend"
    auth_login(request, user, backend=backend)



def verify_2fa_sso(request):
    """Verifica el código TOTP dentro del flujo SSO antes de redirigir al tenant."""
    uid = request.session.get("twofa_pending_uid")
    next_path = request.session.get("twofa_next") or "/"
    client_id = request.session.get("twofa_client_id")

    if not uid or not client_id:
        return HttpResponseForbidden("Sesión de 2FA inválida.")
    current_tenant = get_tenant(request)
    if not current_tenant or current_tenant.pk != client_id:
        return HttpResponseForbidden('Espacio de 2FA inválido.')
    if not TenantMembership.objects.filter(user_id=uid, client_id=client_id, is_active=True).exists():
        return HttpResponseForbidden('Acceso al espacio revocado.')

    user = User.objects.filter(pk=uid).first()
    if not user:
        return HttpResponseForbidden("Usuario no válido.")

    # --- GET: mostrar form si YA HAY otp_secret; si falta => ir a QR ---
    if request.method == "GET":
        policy = TenantSettings.for_client(current_tenant)
        if not user.otp_secret or (policy and policy.multifactor_status == MultiFactorStatus.REQUIRED and not user.is_2fa_enabled):
            enrol_url = reverse("show-qr-code-2fa")
            return redirect(f"{enrol_url}?next={urlquote(next_path)}&sso=1&uid={user.id}")

        # Mostrar el form de verificación (podés reutilizar qr_2fa.html o tener un template aparte)
        return render(request, "qr_2fa.html", {
            "next": next_path,
            "user_email": user.email,
            "verify_url": reverse('verify_2fa_sso'),
            "code_field": 'code',
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
        if ts := TenantSettings.for_client(Client.objects.get(pk=client_id)):
            if ts.multifactor_status == MultiFactorStatus.REQUIRED and not user.is_2fa_enabled:
                user.is_2fa_enabled = True
                user.save(update_fields=['is_2fa_enabled'])

        # limpiar sesión sso-2fa
        for k in ("twofa_pending_uid", "twofa_next", "twofa_client_id"):
            request.session.pop(k, None)

        _login_with_backend(request, user)
        request.session['is_2fa_verified'] = True
        request.session['twofa_verified_user_id'] = user.pk
        request.session['twofa_verified_client_id'] = client_id
        return redirect(next_path)

    # Código inválido: re-render con error (sin exponer otp_secret)
    return render(request, "qr_2fa.html", {
        "error": "Código inválido o expirado. Probá nuevamente.",
        "next": next_path,
        "user_email": user.email,
        "verify_url": reverse('verify_2fa_sso'),
        "code_field": 'code',
    }, status=403)
