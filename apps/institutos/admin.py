"""Institutos en el admin. Permisos por `puede()` y cambios en la bitácora (CatalogoAdmin)."""

from django.contrib import admin

from apps.core.admin import CatalogoAdmin

from .models import AutoridadInstituto, Instituto, ObservacionDato, Ubicacion


@admin.register(Instituto)
class InstitutoAdmin(CatalogoAdmin):
    list_display = ["numero", "nombre", "region", "provincia", "municipio", "precision"]
    list_filter = ["region", "precision", "dependencia", "unidad"]
    search_fields = ["nombre", "municipio"]
    # La ubicación se cambia desde la ficha (deja historial); aquí es de solo lectura.
    readonly_fields = ["lat", "lon", "precision", "institucion"]


@admin.register(ObservacionDato)
class ObservacionDatoAdmin(CatalogoAdmin):
    list_display = ["instituto", "texto", "resuelta"]
    list_filter = ["resuelta", "origen"]
    search_fields = ["texto", "instituto__nombre"]
    fields = ["instituto", "texto", "origen", "resuelta", "respuesta"]
    readonly_fields = ["instituto", "texto", "origen"]


@admin.register(AutoridadInstituto)
class AutoridadInstitutoAdmin(CatalogoAdmin):
    """Dato personal: solo administración de catálogos (el auditor no ve teléfonos)."""

    list_display = ["instituto", "cargo", "nombre", "vigente"]
    search_fields = ["nombre", "instituto__nombre"]

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Ubicacion)
class UbicacionAdmin(CatalogoAdmin):
    list_display = ["instituto", "lat", "lon", "precision", "fuente", "creado_en"]
    list_filter = ["precision"]

    def has_add_permission(self, request):
        return False  # se registran desde la ficha

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
