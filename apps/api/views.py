"""Endpoints transversales de la API."""

import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def _verificar_base_de_datos() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        logger.exception("Salud: la base de datos no responde")
        return False


def _verificar_almacenamiento() -> bool:
    try:
        # Una consulta de existencia ejercita la conexión al almacenamiento (S3 o disco).
        default_storage.exists("salud/.ping")
        return True
    except Exception:
        logger.exception("Salud: el almacenamiento no responde")
        return False


@require_GET
def salud(request):
    """Healthcheck sin autenticación. No expone datos internos ni mensajes de error."""
    base_ok = _verificar_base_de_datos()
    almacen_ok = _verificar_almacenamiento()
    ok = base_ok and almacen_ok
    cuerpo = {
        "estado": "ok" if ok else "error",
        "base_de_datos": "ok" if base_ok else "error",
        "almacenamiento": "ok" if almacen_ok else "error",
        "version": settings.VERSION,
    }
    return JsonResponse(cuerpo, status=200 if ok else 503)
