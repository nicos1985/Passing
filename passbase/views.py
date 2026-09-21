from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from login.models import CustomUser
from notifications.models import UserNotifications
from permission.models import ContraPermission
from .access import CredentialAccessMixin, CredentialOwnerMixin, superadmin_required, visible_credentials
from .forms import ContrasenaForm, ContrasenaUForm, SectionForm
from .models import Contrasena, LogData, SeccionContra


def audit_credential(user, credential, action):
    LogData.objects.create(
        contraseña=credential.pk, entidad='Contraseña', usuario=user, action=action,
        password=credential.contraseña,
        detail=f'Nombre: {credential.nombre_contra}, Usuario: {credential.usuario}, '
               f'Link: {credential.link}, Info: {credential.info}',
    )


class ContrasListView(LoginRequiredMixin, ListView):
    template_name = 'listpass.html'
    context_object_name = 'query_perm'

    def get_queryset(self):
        credentials = visible_credentials(self.request.user).select_related('seccion').order_by('seccion')
        for credential in credentials:
            credential.decrypted_user = credential.get_decrypted_user()
            credential.decrypted_password = credential.get_decrypted_password()
        return credentials

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'title': 'Lista de Contraseñas'}


class ContrasDetailView(CredentialAccessMixin, LoginRequiredMixin, DetailView):
    model = Contrasena
    template_name = 'detail-cont.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = self.object
        credential.decrypted_user = credential.get_decrypted_user()
        credential.decrypted_password = credential.get_decrypted_password()
        logs = list(LogData.objects.filter(contraseña=credential.pk, entidad='Contraseña').order_by('-created')[:10])
        for entry in logs:
            entry.password = entry.get_decrypted_password() if entry.password else ''
            encrypted_user = entry.get_encrypted_user()
            if encrypted_user:
                entry.detail = entry.detail.replace(encrypted_user, entry.get_decrypted_user(encrypted_user))
        context.update({
            'title': 'Detalle de contraseña', 'contraseña': credential, 'log_data': logs,
            'users_permissions': ContraPermission.objects.filter(
                contra_id=credential, permission='True', perm_active=True),
        })
        return context


class ContrasCreateView(LoginRequiredMixin, CreateView):
    model = Contrasena
    form_class = ContrasenaForm
    template_name = 'create-cont.html'
    success_url = reverse_lazy('listpass')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'title': 'Crear Contraseña',
                'sections': SeccionContra.objects.filter(active=True)}

    @transaction.atomic
    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        audit_credential(self.request.user, self.object, 'Create')
        users = {self.request.user.pk}
        if not self.object.is_personal:
            users.update(CustomUser.objects.filter(
                pk__in=settings.GRAN_PERMISSION_ID_USERS, is_active=True).values_list('pk', flat=True))
        for user_id in users:
            ContraPermission.objects.get_or_create(
                user_id_id=user_id, contra_id=self.object,
                defaults={'permission': 'True', 'perm_active': True})
        return response


class ContrasUpdateView(CredentialAccessMixin, LoginRequiredMixin, UpdateView):
    model = Contrasena
    form_class = ContrasenaUForm
    template_name = 'update-cont.html'
    success_url = reverse_lazy('listpass')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user,
                      decrypted_user=self.object.get_decrypted_user(),
                      decrypted_password=self.object.get_decrypted_password())
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        original = self.get_queryset().get(pk=self.object.pk)
        context.update(title='Editar Contraseña', decrypted_user=original.get_decrypted_user(),
                       decrypted_password=original.get_decrypted_password())
        return context

    @transaction.atomic
    def form_valid(self, form):
        original = self.get_queryset().select_for_update().get(pk=self.object.pk)
        audit_credential(self.request.user, original, 'edit old')
        changed = original.get_decrypted_password() != form.cleaned_data['contraseña']
        response = super().form_valid(form)
        if self.object.is_personal:
            ContraPermission.objects.filter(contra_id=self.object).exclude(user_id=self.object.owner).delete()
        audit_credential(self.request.user, self.object, 'change pass' if changed else 'edit new')
        return response


class ContrasDeleteView(CredentialOwnerMixin, LoginRequiredMixin, DeleteView):
    model = Contrasena
    template_name = 'delete-cont.html'
    success_url = reverse_lazy('listpass')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'title': 'Eliminar Contraseña',
                'entity': 'Contraseñas', 'action': 'Inactive', 'list_url': self.success_url}

    @transaction.atomic
    def form_valid(self, form):
        self.object.active = False
        self.object.save(update_fields=['active'])
        audit_credential(self.request.user, self.object, 'Inactive')
        return redirect(self.success_url)


class DescargarArchivo(CredentialAccessMixin, LoginRequiredMixin, DetailView):
    model = Contrasena

    def get(self, request, *args, **kwargs):
        credential = self.get_object()
        if not credential.file:
            raise Http404
        try:
            return FileResponse(credential.file.open('rb'), as_attachment=True,
                                filename=Path(credential.file.name).name,
                                content_type='application/octet-stream')
        except FileNotFoundError:
            raise Http404


@method_decorator(superadmin_required, name='dispatch')
class SectionCreateView(CreateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'create-sect.html'
    success_url = reverse_lazy('listsection')


@method_decorator(superadmin_required, name='dispatch')
class SectionListView(ListView):
    model = SeccionContra
    template_name = 'listsection.html'


@method_decorator(superadmin_required, name='dispatch')
class SectionUpdateView(UpdateView):
    model = SeccionContra
    form_class = SectionForm
    template_name = 'update-sect.html'
    success_url = reverse_lazy('listsection')


@method_decorator(superadmin_required, name='dispatch')
class SectionDeleteView(DeleteView):
    model = SeccionContra
    template_name = 'delete-sect.html'
    success_url = reverse_lazy('listsection')

    def form_valid(self, form):
        self.object.active = False
        self.object.save(update_fields=['active'])
        return redirect(self.success_url)


@method_decorator(superadmin_required, name='dispatch')
class SectionActiveView(DetailView):
    model = SeccionContra
    template_name = 'active-sect.html'

    def post(self, request, *args, **kwargs):
        section = self.get_object()
        section.active = not section.active
        section.save(update_fields=['active'])
        return redirect('listsection')


@superadmin_required
@require_POST
@transaction.atomic
def denypermission(request, pk):
    permission = get_object_or_404(ContraPermission, pk=pk, contra_id__is_personal=False)
    permission.permission = 'False'
    permission.perm_active = False
    permission.save(update_fields=['permission', 'perm_active'])
    UserNotifications.objects.create(id_contrasena=permission.contra_id, id_user=permission.user_id,
                                     type_notification='Acceso revocado', comment='Se revocó el permiso.')
    messages.success(request, 'Permiso revocado.')
    return redirect('permissionlist')
