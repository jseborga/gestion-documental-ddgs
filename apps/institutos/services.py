"""Escritura del módulo de institutos (bitácora y evento en cada cambio)."""

import hashlib
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.auditoria import services as bitacora
from apps.core import services as core_services
from apps.core.models import InstitucionExterna, Proyecto, Unidad
from apps.eventos import services as eventos

from .models import (
    AutoridadInstituto,
    Carrera,
    DerechoPropietario,
    Instituto,
    Matricula,
    ObservacionDato,
    Precision,
    ResolucionMinisterial,
    TechoPresupuestario,
    Ubicacion,
)

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


# --- Importación ----------------------------------------------------------------------


@dataclass
class InformeImportacion:
    institutos_nuevos: int = 0
    institutos_actualizados: int = 0
    proyectos: int = 0
    carreras: int = 0
    observaciones: list[tuple[int | None, str]] = field(default_factory=list)
    simulacion: bool = False

    def resumen(self) -> str:
        modo = "SIMULACIÓN (no se guardó nada)" if self.simulacion else "Importación aplicada"
        return (
            f"{modo}: {self.institutos_nuevos} institutos nuevos, "
            f"{self.institutos_actualizados} actualizados, {self.proyectos} proyectos, "
            f"{self.carreras} carreras, {len(self.observaciones)} observaciones."
        )


class _Revertir(Exception):
    """Se lanza al final de una simulación para deshacer todo."""


def _codigo_proyecto(numero: int, proyecto) -> str:
    clave = f"{proyecto.tipo}|{proyecto.nombre}|{proyecto.gestion_inicio}"
    return f"INST-{numero:03d}-{hashlib.sha256(clave.encode()).hexdigest()[:10]}"


def importar(*, lectura, unidad: Unidad, actor=None, simular: bool = False) -> InformeImportacion:
    """Aplica una lectura de planillas en una sola transacción (o la simula y deshace)."""
    informe = InformeImportacion(simulacion=simular, observaciones=list(lectura.observaciones))
    try:
        with transaction.atomic():
            _aplicar(lectura, unidad, actor, informe)
            bitacora.registrar(
                accion="institutos_importados",
                actor=actor,
                objeto_tipo="importacion",
                objeto_id="institutos",
                despues={
                    "resumen": informe.resumen(),
                    "huellas_sha256": lectura.huellas,
                    "unidad": unidad.sigla,
                },
            )
            eventos.publicar(
                tipo="institutos.importados",
                agregado="importacion",
                agregado_id="institutos",
                payload={
                    "nuevos": informe.institutos_nuevos,
                    "actualizados": informe.institutos_actualizados,
                },
            )
            if simular:
                raise _Revertir
    except _Revertir:
        pass
    return informe


def _aplicar(lectura, unidad: Unidad, actor, informe: InformeImportacion) -> None:
    por_numero: dict[int, Instituto] = {}
    for numero, leido in sorted(lectura.institutos.items()):
        institucion, _ = core_services.guardar_institucion(
            codigo=f"INST-{numero:03d}",
            actor=actor,
            tipo=InstitucionExterna.Tipo.INSTITUTO,
            nombre=leido.nombre,
            municipio=leido.municipio,
        )
        datos = {
            "institucion": institucion,
            "unidad": unidad,
            "nombre": leido.nombre,
            "es_subsede": leido.es_subsede,
            "region": leido.region,
            "provincia": leido.provincia,
            "municipio": leido.municipio,
            "direccion": leido.direccion,
            "situacion": leido.situacion,
            "dependencia_texto": leido.dependencia_texto,
            "dependencia": _dependencia(leido.dependencia_texto),
        }
        instituto, creado = Instituto.objects.update_or_create(numero=numero, defaults=datos)
        por_numero[numero] = instituto
        if creado:
            informe.institutos_nuevos += 1
        else:
            informe.institutos_actualizados += 1

        if leido.rector:
            instituto.autoridades.exclude(nombre=leido.rector).update(vigente=False)
            AutoridadInstituto.objects.update_or_create(
                instituto=instituto,
                nombre=leido.rector,
                defaults={"telefono": leido.telefono, "vigente": True, "cargo": "Rector(a)"},
            )
        if leido.resolucion:
            ResolucionMinisterial.objects.update_or_create(
                instituto=instituto,
                texto=leido.resolucion,
                defaults={"anio": leido.resolucion_anio},
            )
        if leido.en_ficha:
            DerechoPropietario.objects.update_or_create(
                instituto=instituto,
                defaults={
                    "estado": leido.derecho_estado,
                    "folio_real": leido.folio_real,
                    "detalle": leido.derecho_texto,
                },
            )
        if leido.estudiantes is not None and lectura.matricula_anio:
            Matricula.objects.update_or_create(
                instituto=instituto,
                anio=lectura.matricula_anio,
                mes=lectura.matricula_mes,
                fuente="planilla de datos",
                defaults={"estudiantes": leido.estudiantes},
            )
        for nombre in leido.carreras:
            Carrera.objects.get_or_create(instituto=instituto, nombre=nombre)
            informe.carreras += 1
        if leido.techo_bs is not None and lectura.techo_gestion:
            TechoPresupuestario.objects.update_or_create(
                instituto=instituto,
                gestion=lectura.techo_gestion,
                defaults={"monto_bs": leido.techo_bs},
            )
        for proyecto in leido.proyectos:
            core_services.guardar_proyecto(
                codigo=_codigo_proyecto(numero, proyecto),
                unidad=unidad,
                actor=actor,
                nombre=proyecto.nombre,
                tipo=proyecto.tipo,
                instituto=institucion,
                municipio=leido.municipio,
                gestion_inicio=proyecto.gestion_inicio,
                gestion_fin=proyecto.gestion_fin,
                presupuesto_bs=proyecto.presupuesto_bs,
                estado=proyecto.estado if proyecto.estado in Proyecto.Estado.values else "sin_dato",
                estado_detalle=proyecto.estado_texto,
            )
            informe.proyectos += 1

    for numero, texto in informe.observaciones:
        ObservacionDato.objects.get_or_create(
            instituto=por_numero.get(numero) if numero is not None else None,
            texto=texto[:500],
            origen="importacion",
        )


def _dependencia(texto: str) -> str:
    t = texto.lower()
    if "convenio" in t:
        return Instituto.Dependencia.CONVENIO
    if "fiscal" in t:
        return Instituto.Dependencia.FISCAL
    if "privad" in t:
        return Instituto.Dependencia.PRIVADO
    return Instituto.Dependencia.SIN_DATO
