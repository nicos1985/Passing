"""Mixins reutilizables para proteger vistas dentro de un tenant."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.contrib import messages
from .utils import user_belongs_to_current_tenant, users_for_current_tenant

class TenantScopedUserMixin:
    """
    Restringe CustomUser a quienes pertenezcan al tenant actual.
    """
    def get_queryset(self):
        return super().get_queryset().filter(pk__in=users_for_current_tenant().values('pk'))

    def ensure_target_in_tenant(self, user_obj):
        if not user_belongs_to_current_tenant(user_obj):
            raise PermissionDenied("No podés operar usuarios de otro tenant.")


class Safe404RedirectMixin:
    """
    Captura Http404 lanzado dentro de la CBV (p.ej. get_object / get_queryset)
    y redirige mostrando un mensaje.
    """
    not_found_message = "No se encontró el recurso solicitado o no tenés permisos para verlo."
    redirect_url_name = "userlist"  # destino por defecto

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            messages.error(request, self.not_found_message)
            return redirect(self.redirect_url_name)
