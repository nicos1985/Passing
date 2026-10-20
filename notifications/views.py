"""Vistas y helpers que generan las notificaciones de compartición de contraseñas."""

from django.contrib import messages
from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.db.models.query import QuerySet
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views import View
from login.models import CustomUser
from notifications.forms import CreateNotificationForm
from notifications.models import AdminNotification, InboxNotification, UserNotifications
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from passbase.models import Contrasena
from passbase.access import accessible_credentials
from permission.models import ContraPermission
from django.db.models import Case, When, Value, IntegerField
from supporthub.telegram_events import queue_password_request


def can_view_contrasena(user, request):
    """Indica si el usuario puede ver la contraseña solicitada."""
    contrasena_id = int(request.GET.get('contrasena'))
    return accessible_credentials(user).filter(pk=contrasena_id, is_personal=False).exists()

def is_administrator(user):
    """Determina si el usuario pertenece al staff o es superusuario."""
    return user.is_superuser or user.is_staff


@login_required
def notification_inbox(request):
    notices = InboxNotification.objects.filter(user=request.user).order_by('-created_at')
    page = Paginator(notices, 20).get_page(request.GET.get('page'))
    if is_administrator(request.user):
        legacy_count = AdminNotification.objects.filter(type_user=1, viewed=False, id_contrasena__is_personal=False).count()
        legacy_url = reverse('listnotifadmin')
        legacy_label = 'Solicitudes de contraseñas pendientes'
    else:
        legacy_count = UserNotifications.objects.filter(id_user=request.user, viewed=False, id_contrasena_id__in=accessible_credentials(request.user)).count()
        legacy_url = reverse('listnotifuser')
        legacy_label = 'Avisos de contraseñas sin leer'
    return render(request, 'notification_inbox.html', {
        'page': page, 'legacy_count': legacy_count,
        'legacy_url': legacy_url, 'legacy_label': legacy_label,
    })


@login_required
@require_POST
def open_inbox_notice(request, pk):
    notice = get_object_or_404(InboxNotification, pk=pk, user=request.user)
    if not notice.viewed:
        notice.viewed = True
        notice.save(update_fields=['viewed'])
    destination = notice.target_path
    return redirect(destination if destination.startswith('/') and not destination.startswith('//') else 'notification_inbox')


@login_required
@require_POST
def mark_inbox_read(request):
    InboxNotification.objects.filter(user=request.user, viewed=False).update(viewed=True)
    return redirect('notification_inbox')


@login_required
def notification_settings(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    import os
    from supporthub.forms import BotTokenForm
    from supporthub.models import TelegramBotConfig, TelegramRecipient

    bot = TelegramBotConfig.objects.filter(pk=1).first()
    source = ('passing' if bot and bot.token_encrypted else
              'environment' if os.getenv('SUPPORT_TELEGRAM_BOT_TOKEN', '').strip() else None)
    return render(request, 'notification_settings.html', {
        'telegram_bot_source': source,
        'telegram_bot_form': BotTokenForm(),
        'telegram_recipients': TelegramRecipient.objects.select_related('user').all(),
        'telegram_discovered_chats': request.session.pop('telegram_discovered_chats', None),
        'smtp_ready': settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend'
                      and bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD),
        'email_host': settings.EMAIL_HOST,
        'email_port': settings.EMAIL_PORT,
        'email_from': settings.DEFAULT_FROM_EMAIL,
    })


@login_required
@require_POST
def test_notification_email(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    if not request.user.email:
        messages.error(request, 'Tu cuenta no tiene una dirección de correo para recibir la prueba.')
        return redirect('notification_settings')
    try:
        sent = send_mail(
            '[Passing] Correo de prueba',
            'Esta es una prueba de las notificaciones por correo de Passing.',
            settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False,
            connection=get_connection(timeout=10),
        )
        if sent != 1:
            raise RuntimeError('Correo no aceptado')
    except Exception:
        messages.error(request, 'No se pudo enviar el correo de prueba. Revisá SMTP en el servidor y sus registros.')
    else:
        messages.success(request, 'Se envió un correo de prueba a tu cuenta.')
    return redirect('notification_settings')

@login_required
def share_contrasena_form(request, contrasena):
    """Recibe la solicitud de compartir y crea notificación para admins."""
    contrasena_obj = get_object_or_404(
        accessible_credentials(request.user), pk=contrasena, is_personal=False,
    )
    if request.method == 'POST':
        form = CreateNotificationForm(request.POST)
        if form.is_valid():
            share = form.cleaned_data['id_user_share']
            comment = form.cleaned_data['comment']

            obj_permission = ContraPermission.objects.filter(user_id=share, contra_id=contrasena, permission=True).first()
            if not obj_permission:
                notification, created = AdminNotification.objects.get_or_create(
                    id_contrasena=contrasena_obj,
                    id_user_share=share,
                    defaults={
                        'id_user': request.user.username,
                        'type_notification': 'Compartir Contraseña',
                        'action': 'Permiso a contraseña',
                        'comment': comment,
                        'viewed': False,
                    }
                )
               
                if created:
                    queue_password_request(notification.pk)
                    message = f'Se ha solicitado compartir la contraseña "{contrasena_obj.nombre_contra}" con el usuario {share}.'
                    messages.success(request, message)
                else:
                    message = f'Ya existe una solicitud para compartir la contraseña "{contrasena_obj.nombre_contra}" con el usuario {share}. Si no fue atendida la solicitud comuníquese con el administrador.'
                    messages.warning(request, message)
            else:
                message = f'El usuario {share} ya puede visualizar la contraseña "{contrasena_obj.nombre_contra}".'
                messages.success(request, message)
            
            return redirect('listpass')
        else:
            messages.error(request, 'Hay errores en el formulario, por favor verifica los campos.')
    else:
        form = CreateNotificationForm()
    
    return render(request, 'create-noti-admin.html', {'form': form})

class ListNotificationsUser(LoginRequiredMixin, ListView):
    model =UserNotifications
    template_name = 'user-noti-list.html'
    context_object_name = 'notifications'
    login_url = 'login'
    
    """Lista las notificaciones del usuario ordenadas por estado."""
    
    def get_queryset(self):
        
        queryset = UserNotifications.objects.filter(id_user=self.request.user, id_contrasena_id__in=accessible_credentials(self.request.user)).order_by('viewed', '-created')
        return queryset

    
class MarkNotificationsViewed(LoginRequiredMixin, View):
    """Marca como vistas las notificaciones del usuario vía AJAX."""
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if not request.user.is_authenticated:
                return HttpResponseForbidden("No autorizado")
            notifications = UserNotifications.objects.filter(id_user=request.user)
            for noti in notifications:
                noti.viewed = True
                noti.save()
            return JsonResponse({'status': 'success'})
        return HttpResponseForbidden("No autorizado")    



class ListNotificationsAdmin(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Lista las solicitudes pendientes para admins y staff."""

    model = AdminNotification
    template_name = 'admin-noti-list.html'
    context_object_name = 'notifications'
    login_url = 'login'

    def get_queryset(self):
        return AdminNotification.objects.filter(id_contrasena__is_personal=False, id_contrasena__active=True)

    def test_func(self):
        return is_administrator(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta página.")
        return redirect('listpass')

class UpdateNotificationsUser():
    """Placeholder para futuras acciones sobre notificaciones de usuario."""
    pass

class UpdateNotificationsAdmin():
    """Espacio reservado para editar notificaciones de admins en un futuro."""
    pass

