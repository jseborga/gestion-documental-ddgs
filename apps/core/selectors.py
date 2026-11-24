"""Consultas de solo lectura de los catálogos. Otras apps leen core por aquí."""

import datetime as dt

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Cargo, Feriado, OcupacionCargo, Persona


def _hoy() -> dt.date:
    return timezone.localdate()


def _vigente_en(fecha: dt.date) -> Q:
    return Q(desde__lte=fecha) & (Q(hasta__isnull=True) | Q(hasta__gte=fecha))


def cargos_vigentes(persona: Persona, fecha: dt.date | None = None) -> QuerySet[Cargo]:
    """Cargos que la persona ocupa en la fecha (titular, interino o suplente).

    La bandeja de una persona se arma con estos cargos (SPEC.md §6.6), así que una
    suplencia aparece y desaparece sola según sus fechas.
    """
    fecha = fecha or _hoy()
    ocupaciones = OcupacionCargo.objects.filter(_vigente_en(fecha), persona=persona)
    return (
        Cargo.objects.filter(activo=True, ocupaciones__in=ocupaciones)
        .select_related("unidad")
        .distinct()
    )


def ocupaciones_vigentes(cargo: Cargo, fecha: dt.date | None = None) -> QuerySet[OcupacionCargo]:
    fecha = fecha or _hoy()
    return OcupacionCargo.objects.filter(_vigente_en(fecha), cargo=cargo).select_related("persona")


def titular_se_solapa(
    cargo: Cargo, desde: dt.date, hasta: dt.date | None, excluir_id: int | None = None
) -> bool:
    """¿Hay otro titular del cargo cuyo periodo se cruza con [desde, hasta]?"""
    consulta = OcupacionCargo.objects.filter(cargo=cargo, tipo=OcupacionCargo.Tipo.TITULAR).filter(
        Q(hasta__isnull=True) | Q(hasta__gte=desde)
    )
    if hasta is not None:
        consulta = consulta.filter(desde__lte=hasta)
    if excluir_id is not None:
        consulta = consulta.exclude(pk=excluir_id)
    return consulta.exists()


def es_dia_habil(fecha: dt.date) -> bool:
    return fecha.weekday() < 5 and not Feriado.objects.filter(fecha=fecha).exists()


def sumar_dias_habiles(inicio: dt.date, dias: int) -> dt.date:
    """Fecha que resulta de contar `dias` hábiles después de `inicio` (sin contar `inicio`).

    Fines de semana y feriados registrados no cuentan. Con `dias=0` devuelve `inicio`.
    """
    if dias < 0:
        raise ValueError("Los días hábiles a sumar no pueden ser negativos.")
    # Un año de margen alcanza para cualquier plazo administrativo razonable.
    feriados = set(
        Feriado.objects.filter(
            fecha__gt=inicio, fecha__lte=inicio + dt.timedelta(days=dias * 3 + 366)
        ).values_list("fecha", flat=True)
    )
    fecha = inicio
    restantes = dias
    while restantes > 0:
        fecha += dt.timedelta(days=1)
        if fecha.weekday() < 5 and fecha not in feriados:
            restantes -= 1
    return fecha
