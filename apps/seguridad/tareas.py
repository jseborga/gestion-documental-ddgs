"""Tareas periódicas del worker relacionadas con seguridad."""

import datetime as dt

from django.conf import settings
from django.utils import timezone

from apps.auditoria import selectors as bitacora_lectura
from apps.auditoria import services as bitacora
from apps.eventos.services import tarea_periodica

from . import services


@tarea_periodica("desactivar_cuentas_sin_cargo", cada=dt.timedelta(hours=24))
def desactivar_cuentas() -> str:
    desactivadas = services.desactivar_cuentas_sin_cargo()
    return f"{len(desactivadas)} cuentas desactivadas"


@tarea_periodica("vigilar_respaldo", cada=dt.timedelta(hours=1))
def vigilar_respaldo() -> str:
    """Alerta (una vez al día) si no hay un respaldo exitoso reciente."""
    if not settings.RESPALDO_VIGILAR:
        return "vigilancia desactivada"
    limite = timezone.now() - dt.timedelta(hours=settings.RESPALDO_ALERTA_HORAS)
    ultimo = bitacora_lectura.ultimo("respaldo_ok")
    if ultimo is not None and ultimo.creado_en >= limite:
        return f"último respaldo {ultimo.creado_en:%Y-%m-%d %H:%M}"
    if bitacora_lectura.contar_recientes("alerta_sin_respaldo", minutos=24 * 60):
        return "sin respaldo reciente (ya alertado)"
    bitacora.registrar_seguridad(accion="alerta_sin_respaldo")
    services.alertar(
        "No hay respaldo reciente",
        f"No se registró un respaldo exitoso en las últimas {settings.RESPALDO_ALERTA_HORAS} "
        "horas. Revise el servicio 'backup'.",
    )
    return "alerta enviada"
