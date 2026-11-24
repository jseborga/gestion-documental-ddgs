"""Ubicación APROXIMADA por municipio con OpenStreetMap Nominatim.

Solo desde un comando de administrador. Política de uso de Nominatim: máximo 1 petición
por segundo, User-Agent identificable con contacto, resultados en caché. La URL es fija
(no la elige el usuario): no hay riesgo de SSRF.
"""

import json
import time
import urllib.parse
import urllib.request
from decimal import Decimal

from django.conf import settings

URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"
MAX_BYTES_RESPUESTA = 200_000
PAUSA_SEGUNDOS = 1.1


class ErrorGeocodificacion(Exception):
    pass


def _consultar(parametros: dict) -> list:
    if not settings.NOMINATIM_CONTACTO:
        raise ErrorGeocodificacion(
            "Configure NOMINATIM_CONTACTO (correo) antes de consultar Nominatim."
        )
    url = f"{URL_NOMINATIM}?{urllib.parse.urlencode(parametros)}"
    peticion = urllib.request.Request(  # noqa: S310  (URL https fija, ver docstring)
        url,
        headers={
            "User-Agent": f"gestion-documental/{settings.VERSION} ({settings.NOMINATIM_CONTACTO})",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:  # noqa: S310  # nosec B310
        cuerpo = respuesta.read(MAX_BYTES_RESPUESTA + 1)
    if len(cuerpo) > MAX_BYTES_RESPUESTA:
        raise ErrorGeocodificacion("Respuesta demasiado grande.")
    return json.loads(cuerpo)


def buscar_municipio(municipio: str, provincia: str = "") -> tuple[Decimal, Decimal] | None:
    partes = [p for p in (municipio, provincia, settings.INSTITUTOS_REGION_BUSQUEDA) if p]
    resultados = _consultar(
        {
            "q": ", ".join(partes),
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": settings.INSTITUTOS_PAIS,
        }
    )
    if not resultados:
        return None
    try:
        return Decimal(str(resultados[0]["lat"])), Decimal(str(resultados[0]["lon"]))
    except (KeyError, IndexError, ArithmeticError, ValueError):
        return None


def pausa() -> None:
    time.sleep(PAUSA_SEGUNDOS)
