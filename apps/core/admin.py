"""Administración de catálogos. Las ocupaciones de cargo pasan por los servicios."""

from django import forms
from django.contrib import admin

from . import selectors, services
from .models import (
    Cargo,
    Feriado,
    InstitucionExterna,
    OcupacionCargo,
    Persona,
    Proceso,
    Proyecto,
    Unidad,
)


@admin.register(Unidad)
class UnidadAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nombre", "nivel", "padre", "prefijo_cite", "activo"]
    list_filter = ["nivel", "activo"]
    search_fields = ["sigla", "nombre"]


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "unidad", "puede_firmar", "es_ventanilla", "activo"]
    list_filter = ["unidad", "puede_firmar", "es_ventanilla", "activo"]
    search_fields = ["codigo", "nombre"]


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ["apellidos", "nombres", "nombre_corto", "email", "activo"]
    list_filter = ["activo"]
    search_fields = ["apellidos", "nombres", "email"]


class OcupacionCargoForm(forms.ModelForm):
    class Meta:
        model = OcupacionCargo
        fields = ["persona", "cargo", "tipo", "desde", "hasta", "acto_designacion"]

    def clean(self):
        datos = super().clean()
        cargo, tipo = datos.get("cargo"), datos.get("tipo")
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if (
            cargo
            and desde
            and tipo == OcupacionCargo.Tipo.TITULAR
            and selectors.titular_se_solapa(cargo, desde, hasta, excluir_id=self.instance.pk)
        ):
            raise forms.ValidationError("El cargo ya tiene un titular en ese periodo.")
        return datos


@admin.register(OcupacionCargo)
class OcupacionCargoAdmin(admin.ModelAdmin):
    form = OcupacionCargoForm
    list_display = ["persona", "cargo", "tipo", "desde", "hasta", "acto_designacion"]
    list_filter = ["tipo", "cargo__unidad"]
    search_fields = ["persona__apellidos", "cargo__nombre", "acto_designacion"]
    date_hierarchy = "desde"

    def get_readonly_fields(self, request, obj=None):
        # Una ocupación registrada solo se cierra (fecha final); el resto queda como historia.
        if obj is not None:
            return ["persona", "cargo", "tipo", "desde", "acto_designacion"]
        return []

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            creada = services.asignar_cargo(
                persona=obj.persona,
                cargo=obj.cargo,
                tipo=obj.tipo,
                desde=obj.desde,
                hasta=obj.hasta,
                acto_designacion=obj.acto_designacion,
            )
            obj.pk = creada.pk
        elif "hasta" in form.changed_data and obj.hasta is not None:
            services.terminar_ocupacion(ocupacion=obj, hasta=obj.hasta)


@admin.register(InstitucionExterna)
class InstitucionExternaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "sigla", "tipo", "municipio", "activo"]
    list_filter = ["tipo", "activo"]
    search_fields = ["codigo", "nombre", "sigla", "municipio"]


@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "padre", "requiere_proyecto", "plazo_dias_defecto"]
    search_fields = ["codigo", "nombre"]


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "tipo", "instituto", "estado", "presupuesto_bs"]
    list_filter = ["tipo", "estado", "unidad"]
    search_fields = ["codigo", "nombre", "contrato_ref", "codigo_sisin"]
    autocomplete_fields = ["instituto"]


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ["fecha", "nombre", "ambito"]
    list_filter = ["ambito"]
    date_hierarchy = "fecha"
