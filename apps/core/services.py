"""Escritura de catálogos con reglas de negocio.

Nota: la bitácora y el outbox se conectan en el paso 3 (CLAUDE.md); estos servicios
son el único punto donde habrá que agregarlos.
"""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import transaction

from . import selectors
from .models import Cargo, OcupacionCargo, Persona


@transaction.atomic
def asignar_cargo(
    *,
    persona: Persona,
    cargo: Cargo,
    tipo: str,
    desde: dt.date,
    hasta: dt.date | None = None,
    acto_designacion: str = "",
) -> OcupacionCargo:
    """Registra que una persona ocupa un cargo (titular, interino o suplente).

    Reglas: persona y cargo activos; `hasta` no anterior a `desde`; un solo titular
    por cargo en cualquier fecha. Interinos y suplentes pueden coexistir con el titular
    (p. ej. durante vacaciones). Bloquea la fila del cargo para evitar carreras.
    """
    if tipo not in OcupacionCargo.Tipo.values:
        raise ValidationError({"tipo": "Tipo de ocupación no válido."})
    cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
    if not cargo.activo:
        raise ValidationError({"cargo": "El cargo está inactivo."})
    if not persona.activo:
        raise ValidationError({"persona": "La persona está inactiva."})
    if hasta is not None and hasta < desde:
        raise ValidationError({"hasta": "La fecha final no puede ser anterior a la inicial."})
    if tipo == OcupacionCargo.Tipo.TITULAR and selectors.titular_se_solapa(cargo, desde, hasta):
        raise ValidationError(
            {"desde": "El cargo ya tiene un titular en ese periodo. Cierre primero esa ocupación."}
        )
    ocupacion = OcupacionCargo(
        persona=persona,
        cargo=cargo,
        tipo=tipo,
        desde=desde,
        hasta=hasta,
        acto_designacion=acto_designacion,
    )
    ocupacion.full_clean()
    ocupacion.save()
    return ocupacion


@transaction.atomic
def terminar_ocupacion(*, ocupacion: OcupacionCargo, hasta: dt.date) -> OcupacionCargo:
    """Cierra una ocupación en la fecha indicada (último día en el cargo)."""
    ocupacion = OcupacionCargo.objects.select_for_update().get(pk=ocupacion.pk)
    if ocupacion.hasta is not None and ocupacion.hasta <= hasta:
        raise ValidationError({"hasta": "La ocupación ya estaba cerrada en esa fecha o antes."})
    if hasta < ocupacion.desde:
        raise ValidationError({"hasta": "La fecha final no puede ser anterior a la inicial."})
    ocupacion.hasta = hasta
    ocupacion.save(update_fields=["hasta", "actualizado_en"])
    return ocupacion
