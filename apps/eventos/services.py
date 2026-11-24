"""Publicación y procesamiento de eventos del outbox.

`publicar` se llama dentro de la transacción del cambio de negocio: si esta falla,
el evento no existe. El worker procesa con SELECT ... FOR UPDATE SKIP LOCKED, así
que varios workers pueden correr a la vez sin procesar dos veces el mismo evento.
"""

import datetime as dt
import json
import logging
from collections.abc import Callable
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .models import EjecucionTarea, EventoOutbox

logger = logging.getLogger(__name__)

MAX_INTENTOS = 5

Consumidor = Callable[[EventoOutbox], None]
_consumidores: dict[str, list[Consumidor]] = {}

Tarea = Callable[[], str]
_tareas: dict[str, tuple[dt.timedelta, Tarea]] = {}


def suscribir(tipo: str) -> Callable[[Consumidor], Consumidor]:
    """Decorador: registra una función que procesa los eventos de un tipo."""

    def decorador(funcion: Consumidor) -> Consumidor:
        _consumidores.setdefault(tipo, []).append(funcion)
        return funcion

    return decorador


def tarea_periodica(nombre: str, cada: dt.timedelta) -> Callable[[Tarea], Tarea]:
    """Decorador: registra una tarea que el worker ejecuta como máximo una vez por periodo."""

    def decorador(funcion: Tarea) -> Tarea:
        _tareas[nombre] = (cada, funcion)
        return funcion

    return decorador


def publicar(*, tipo: str, agregado: str, agregado_id: str | int, payload: dict | None = None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("publicar() debe llamarse dentro de transaction.atomic().")
    return EventoOutbox.objects.create(
        tipo=tipo,
        agregado=agregado,
        agregado_id=str(agregado_id),
        payload=json.loads(json.dumps(payload or {}, cls=DjangoJSONEncoder)),
    )


def procesar_lote(tamano: int = 50) -> int:
    """Procesa hasta `tamano` eventos pendientes. Devuelve cuántos se marcaron procesados."""
    procesados = 0
    with transaction.atomic():
        eventos = list(
            EventoOutbox.objects.select_for_update(skip_locked=True)
            .filter(procesado_en__isnull=True, intentos__lt=MAX_INTENTOS)
            .order_by("id")[:tamano]
        )
        for evento in eventos:
            try:
                with transaction.atomic():  # cada consumidor en su propio punto de guardado
                    for consumidor in _consumidores.get(evento.tipo, []):
                        consumidor(evento)
                evento.procesado_en = timezone.now()
                evento.ultimo_error = ""
                procesados += 1
            except Exception as error:  # el worker no debe caerse por un evento
                logger.exception("Error procesando el evento %s", evento.pk)
                evento.ultimo_error = f"{type(error).__name__}: {error}"[:2000]
            evento.intentos += 1
            evento.save(update_fields=["procesado_en", "ultimo_error", "intentos"])
    return procesados


def ejecutar_tareas_vencidas(ahora: dt.datetime | None = None) -> list[str]:
    """Ejecuta las tareas periódicas cuyo periodo venció. Devuelve sus nombres."""
    ahora = ahora or timezone.now()
    ejecutadas = []
    for nombre, (cada, funcion) in sorted(_tareas.items()):
        with transaction.atomic():
            registro = (
                EjecucionTarea.objects.select_for_update(skip_locked=True)
                .filter(nombre=nombre)
                .first()
            )
            if registro is None:
                registro, creado = EjecucionTarea.objects.get_or_create(
                    nombre=nombre, defaults={"ultima_ejecucion": ahora - cada}
                )
            if registro.ultima_ejecucion + cada > ahora:
                continue
            try:
                with transaction.atomic():
                    resultado = funcion() or "ok"
            except Exception as error:
                logger.exception("Error en la tarea periódica %s", nombre)
                resultado = f"error: {type(error).__name__}: {error}"
            registro.ultima_ejecucion = ahora
            registro.ultimo_resultado = str(resultado)[:2000]
            registro.save(update_fields=["ultima_ejecucion", "ultimo_resultado"])
            ejecutadas.append(nombre)
    return ejecutadas


def tareas_registradas() -> dict[str, Any]:
    return {nombre: cada for nombre, (cada, _) in _tareas.items()}
