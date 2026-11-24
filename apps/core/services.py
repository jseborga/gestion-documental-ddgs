"""Escritura de catálogos con reglas de negocio.

Cada operación registra la bitácora y publica su evento en la misma transacción.
"""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.auditoria import services as bitacora
from apps.eventos import services as eventos

from . import selectors
from .models import Cargo, InstitucionExterna, OcupacionCargo, Persona, Proyecto, Unidad


@transaction.atomic
def asignar_cargo(
    *,
    persona: Persona,
    cargo: Cargo,
    tipo: str,
    desde: dt.date,
    hasta: dt.date | None = None,
    acto_designacion: str = "",
    actor=None,
    ip: str | None = None,
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
    bitacora.registrar(
        accion="ocupacion_asignada",
        actor=actor,
        objeto=ocupacion,
        despues=bitacora.instantanea(ocupacion),
        ip=ip,
    )
    eventos.publicar(
        tipo="core.ocupacion_asignada",
        agregado="ocupacion_cargo",
        agregado_id=ocupacion.pk,
        payload={"persona": persona.pk, "cargo": cargo.pk, "tipo": tipo, "desde": desde},
    )
    return ocupacion


@transaction.atomic
def terminar_ocupacion(
    *, ocupacion: OcupacionCargo, hasta: dt.date, actor=None, ip: str | None = None
) -> OcupacionCargo:
    """Cierra una ocupación en la fecha indicada (último día en el cargo)."""
    ocupacion = OcupacionCargo.objects.select_for_update().get(pk=ocupacion.pk)
    if ocupacion.hasta is not None and ocupacion.hasta <= hasta:
        raise ValidationError({"hasta": "La ocupación ya estaba cerrada en esa fecha o antes."})
    if hasta < ocupacion.desde:
        raise ValidationError({"hasta": "La fecha final no puede ser anterior a la inicial."})
    antes = bitacora.instantanea(ocupacion, ["hasta"])
    ocupacion.hasta = hasta
    ocupacion.save(update_fields=["hasta", "actualizado_en"])
    bitacora.registrar(
        accion="ocupacion_terminada",
        actor=actor,
        objeto=ocupacion,
        antes=antes,
        despues=bitacora.instantanea(ocupacion, ["hasta"]),
        ip=ip,
    )
    eventos.publicar(
        tipo="core.ocupacion_terminada",
        agregado="ocupacion_cargo",
        agregado_id=ocupacion.pk,
        payload={"hasta": hasta},
    )
    return ocupacion


@transaction.atomic
def guardar_institucion(*, codigo: str, actor=None, **datos) -> tuple[InstitucionExterna, bool]:
    """Crea o actualiza una institución externa por su código, con bitácora."""
    existente = InstitucionExterna.objects.select_for_update().filter(codigo=codigo).first()
    antes = bitacora.instantanea(existente) if existente else None
    institucion, creada = InstitucionExterna.objects.update_or_create(codigo=codigo, defaults=datos)
    despues = bitacora.instantanea(institucion)
    if creada or antes != despues:
        bitacora.registrar(
            accion="institucion_creada" if creada else "institucion_modificada",
            actor=actor,
            objeto=institucion,
            antes=antes,
            despues=despues,
        )
    return institucion, creada


@transaction.atomic
def guardar_proyecto(*, codigo: str, unidad: Unidad, actor=None, **datos) -> tuple[Proyecto, bool]:
    """Crea o actualiza un proyecto por su código, con bitácora y evento."""
    existente = Proyecto.objects.select_for_update().filter(codigo=codigo).first()
    antes = bitacora.instantanea(existente) if existente else None
    proyecto, creado = Proyecto.objects.update_or_create(
        codigo=codigo, defaults={"unidad": unidad, **datos}
    )
    despues = bitacora.instantanea(proyecto)
    if creado or antes != despues:
        bitacora.registrar(
            accion="proyecto_creado" if creado else "proyecto_modificado",
            actor=actor,
            objeto=proyecto,
            antes=antes,
            despues=despues,
        )
        eventos.publicar(
            tipo="core.proyecto_guardado",
            agregado="proyecto",
            agregado_id=proyecto.pk,
            payload={"codigo": codigo, "estado": proyecto.estado},
        )
    return proyecto, creado
