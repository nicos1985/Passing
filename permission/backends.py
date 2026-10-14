"""Permisos de módulos asignados mediante roles propios de cada tenant."""

from django.contrib.auth.backends import BaseBackend
from django.db import connection

from .module_access import MODULE_PERMISSION_CODES


class ModuleRoleBackend(BaseBackend):
    def has_perm(self, user_obj, perm, obj=None):
        if obj is not None or not user_obj.is_authenticated or not user_obj.is_active:
            return False
        keys = MODULE_PERMISSION_CODES.get(perm)
        if not keys or getattr(connection, 'schema_name', 'public') == 'public':
            return False

        from login.utils import user_belongs_to_current_tenant
        from .models import UserRoles

        if not user_belongs_to_current_tenant(user_obj):
            return False
        roles = UserRoles.objects.filter(user=user_obj, rol__is_active=True).values_list(
            'rol__module_permissions', flat=True,
        )
        return any(keys.intersection(role_keys or []) for role_keys in roles)
