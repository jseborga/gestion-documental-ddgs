"""Escritura del módulo de institutos (bitácora y evento en cada cambio)."""

import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.auditoria import services as bitacora
from apps.eventos import services as eventos

from .models import Instituto, Precision, Ubicacion

SEIS = Decimal("0.000001")

# Formatos aceptados sin consultar ningún servidor (sin seguir enlaces: evita SSRF).
_PATRONES = [
    re.compile(r"@(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)"),  # .../@-16.49,-68.13,15z
    re.compile(r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)"),  # ...!3d-16.49!4d-68.13
    re.compile(r"[?&](?:q|query|ll|center)=(-?\d{1,3}\.\d+)(?:,|%2C)\s*(-?\d{1,3}\.\d+)", re.I),
    re.compile(r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$"),  # "lat, lon"
]


def parsear_coordenadas(texto: str) -> tuple[Decimal, Decimal]:
    """Extrae (lat, lon) de coordenadas escritas o de un enlace largo de Google Maps."""
    texto = (texto or "").strip()[:2000]
    if not texto:
        raise ValidationError("Ingrese coordenadas o un enlace de Google Maps.")
    if re.search(r"(goo\.gl|maps\.app\.goo\.gl)/", texto, re.I):
        raise ValidationError(
            "Los enlaces cortos no se pueden leer sin abrirlos. Abra el enlace en el navegador "
            "y copie la dirección completa, o copie las coordenadas."
        )
    for patron in _PATRONES:
        coincidencia = patron.search(texto)
        if coincidencia:
            try:
                lat = Decimal(coincidencia.group(1).replace(",", "."))
                lon = Decimal(coincidencia.group(2).replace(",", "."))
            except InvalidOperation as error:
                raise ValidationError("Coordenadas no válidas.") from error
            return lat, lon
    raise ValidationError("No se encontraron coordenadas en el texto.")


def validar_en_zona(lat: Decimal, lon: Decimal) -> None:
    lat_min, lat_max, lon_min, lon_max = settings.INSTITUTOS_ZONA
    if not (lat_min <= float(lat) <= lat_max and lon_min <= float(lon) <= lon_max):
        raise ValidationError(
            "La ubicación está fuera de la zona de trabajo configurada. "
            "Revise si invirtió latitud y longitud o el signo negativo."
        )


@transaction.atomic
def registrar_ubicacion(
    *,
    instituto: Instituto,
    lat: Decimal,
    lon: Decimal,
    precision: str,
    fuente: str = "",
    actor=None,
    ip: str | None = None,
) -> Ubicacion:
    if precision not in Precision.values or precision == Precision.PENDIENTE:
        raise ValidationError({"precision": "Precisión no válida."})
    lat = Decimal(lat).quantize(SEIS)
    lon = Decimal(lon).quantize(SEIS)
    validar_en_zona(lat, lon)
    instituto = Instituto.objects.select_for_update().get(pk=instituto.pk)
    antes = {"lat": instituto.lat, "lon": instituto.lon, "precision": instituto.precision}
    ubicacion = Ubicacion.objects.create(
        instituto=instituto,
        lat=lat,
        lon=lon,
        precision=precision,
        fuente=fuente[:200],
        registrado_por=actor if getattr(actor, "is_authenticated", False) else None,
    )
    instituto.lat, instituto.lon, instituto.precision = lat, lon, precision
    instituto.save(update_fields=["lat", "lon", "precision", "actualizado_en"])
    bitacora.registrar(
        accion="ubicacion_registrada",
        actor=actor,
        objeto=instituto,
        antes=antes,
        despues={"lat": lat, "lon": lon, "precision": precision, "fuente": fuente[:200]},
        ip=ip,
    )
    eventos.publicar(
        tipo="institutos.ubicacion_registrada",
        agregado="instituto",
        agregado_id=instituto.pk,
        payload={"precision": precision},
    )
    return ubicacion
