"""Usuarios y roles en el admin, gobernados por `puede()` y registrados en la bitácora."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from apps.auditoria import services as bitacora

from . import services
from .permisos import Accion, puede
from .red import ip_cliente

Usuario = get_user_model()
CAMPOS_AUDITADOS = ["username", "email", "is_active", "is_staff", "is_superuser"]

admin.site.unregister(Usuario)
admin.site.unregister(Group)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ["username", "email", "is_active", "is_staff", "last_login"]
    list_filter = ["is_active", "is_staff", "groups"]

    def _gestiona(self, request):
        return puede(request.user, Accion.GESTIONAR_USUARIOS)

    def has_module_permission(self, request):
        return self._gestiona(request)

    def has_view_permission(self, request, obj=None):
        return self._gestiona(request) or puede(request.user, Accion.VER_BITACORA)

    def has_add_permission(self, request):
        return self._gestiona(request)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False  # nadie sin ser superusuario modifica a un superusuario
        return self._gestiona(request)

    def has_delete_permission(self, request, obj=None):
        return False  # las cuentas se desactivan, no se borran (trazabilidad)

    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            # Evita la escalada de privilegios desde el rol administrador.
            campos += ["is_superuser", "user_permissions", "is_staff", "last_login", "date_joined"]
            if obj is not None and obj.pk == request.user.pk:
                campos += ["groups", "is_active"]  # nadie cambia sus propios roles
        return campos

    def save_model(self, request, obj, form, change):
        antes = None
        if change:
            anterior = Usuario.objects.filter(pk=obj.pk).first()
            antes = bitacora.instantanea(anterior, CAMPOS_AUDITADOS) if anterior else None
        super().save_model(request, obj, form, change)
        bitacora.registrar_seguridad(
            accion="usuario_modificado" if change else "usuario_creado",
            actor=request.user,
            objeto=obj,
            antes=antes,
            despues=bitacora.instantanea(obj, CAMPOS_AUDITADOS),
            ip=ip_cliente(request),
        )

    def save_related(self, request, form, formsets, change):
        antes = sorted(form.instance.groups.values_list("name", flat=True)) if change else []
        super().save_related(request, form, formsets, change)
        despues = sorted(form.instance.groups.values_list("name", flat=True))
        if antes != despues:
            privilegiados = {"administrador", "director", "auditor"}
            if (set(antes) ^ set(despues)) & privilegiados:
                services.alertar(
                    "Cambio de rol privilegiado",
                    f"'{request.user.get_username()}' cambió los roles de "
                    f"'{form.instance.get_username()}': {antes} -> {despues}.",
                )
            bitacora.registrar_seguridad(
                accion="roles_modificados",
                actor=request.user,
                objeto=form.instance,
                antes={"roles": antes},
                despues={"roles": despues},
                ip=ip_cliente(request),
            )


@admin.register(Group)
class RolAdmin(admin.ModelAdmin):
    """Los roles se definen por migración; aquí solo se consultan."""

    list_display = ["name"]

    def has_module_permission(self, request):
        return puede(request.user, Accion.GESTIONAR_USUARIOS)

    def has_view_permission(self, request, obj=None):
        return puede(request.user, Accion.GESTIONAR_USUARIOS)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
