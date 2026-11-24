"""Bitácora de solo lectura en el admin."""

from django.contrib import admin

from .models import Bitacora


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ["creado_en", "categoria", "actor_nombre", "accion", "objeto_tipo", "objeto_id"]
    list_filter = ["categoria", "accion"]
    search_fields = ["accion", "objeto_tipo", "objeto_id", "actor_nombre"]
    date_hierarchy = "creado_en"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        from apps.seguridad.permisos import puede

        return puede(request.user, "ver_bitacora")
