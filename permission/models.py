"""Modelos para permisos, roles y asignación de roles a usuarios.

- `ContraPermission`: permisos individuales por usuario y contraseña.
- `PermissionRoles`: agrupa contraseñas bajo un rol reutilizable.
- `UserRoles`: asigna un `PermissionRoles` a un usuario.
"""

from django.db import models
from login.models import CustomUser
from passbase.models import Contrasena
from django.utils.translation import gettext_lazy as _


class ContraPermission(models.Model):
    """Permiso explícito que relaciona un `CustomUser` con una `Contrasena`.

    `permission` puede almacenar estado textual; `perm_active` indica si está vigente.
    """

    user_id = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name=_('Usuario'))
    contra_id = models.ForeignKey(Contrasena, on_delete=models.CASCADE, verbose_name=_('Contraseña'))
    permission = models.CharField(max_length=20, blank=True, verbose_name=_('Permiso'))
    perm_active = models.BooleanField(default=True, verbose_name=_('Permiso activo'))
    created = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))
    updated = models.DateTimeField(auto_now_add=True, verbose_name=_('Actualizado'))

    class Meta:
        verbose_name = _('Permiso')
        verbose_name_plural = _('Permisos')

    def __str__(self):
        return str(self.user_id.username)


class PermissionRoles(models.Model):
    """Rol que agrupa múltiples `Contrasena` para asignación masiva de permisos."""

    rol_name = models.CharField(max_length=60, verbose_name=_('Nombre del rol'))
    contrasenas = models.ManyToManyField(Contrasena, related_name='roles', verbose_name=_('Contraseñas'))
    comment = models.CharField(max_length=200, blank=True, verbose_name=_('Comentario'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))
    created = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))

    def __str__(self):
        return self.rol_name

    def get_contrasenas(self):
        """Devuelve el queryset de contraseñas asociadas al rol."""
        return self.contrasenas.all()

    def get_contrasenas_not_personal(self):
        """Filtra las contraseñas públicas (no personales)."""
        return self.contrasenas.filter(is_personal=False)

    def inactive(self):
        """Marca el rol como inactivo y persiste el cambio."""
        self.is_active = False
        self.save()
        return self.is_active


class UserRoles(models.Model):
    """Asociación simple entre `CustomUser` y `PermissionRoles`."""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name=_('Usuario'))
    rol = models.ForeignKey(PermissionRoles, on_delete=models.CASCADE, verbose_name=_('Rol'))
    created = models.DateTimeField(auto_now=True, verbose_name=_('Creado'))

    def __str__(self):
        return f'User: {self.user.username}, rol: {self.rol.rol_name}'