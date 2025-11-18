
from django.db import connection
from django.core.exceptions import PermissionDenied
from client.models import Client
from accounts.models import TenantMembership
from django.http import Http404
from django.shortcuts import redirect
from django.contrib import messages

class TenantScopedUserMixin:
    """
    Restringe CustomUser a quienes tengan memberships activos en el tenant actual.
    Usa la relación inversa correcta: `memberships` (no tenantmembership).
    """
    def get_current_client(self):
        schema = getattr(connection, "schema_name", None)
        return Client.objects.get(schema_name=schema)

    def get_queryset(self):
        qs = super().get_queryset()
        client = self.get_current_client()
        return (qs.filter(
                    memberships__client=client,         # <─ FIX
                    memberships__is_active=True         # <─ FIX
                )
                .select_related()  # opcional
                .distinct())

    def ensure_target_in_tenant(self, user_obj):
        client = self.get_current_client()
        ok = TenantMembership.objects.filter(
            user=user_obj, client=client, is_active=True
        ).exists()
        if not ok:
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