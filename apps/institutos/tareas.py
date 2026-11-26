"""Trabajo en segundo plano del módulo (lo ejecuta el worker a partir de eventos)."""

from apps.auditoria import services as bitacora
from apps.eventos.services import suscribir

from . import geocodificacion, services

EVENTO_APROXIMAR = "institutos.aproximar_solicitado"


@suscribir(EVENTO_APROXIMAR)
def aproximar(evento) -> None:
    """Ubicación aproximada pedida desde la web. No reintenta errores de configuración."""
    try:
        informe = services.aproximar_ubicaciones(maximo=int(evento.payload.get("maximo", 100)))
        accion, detalle = "ubicaciones_aproximadas", {"resumen": informe.resumen()}
    except geocodificacion.ErrorGeocodificacion as error:
        accion, detalle = "ubicaciones_aproximadas_error", {"error": str(error)}
    except OSError as error:
        accion, detalle = "ubicaciones_aproximadas_error", {"error": f"Sin conexión: {error}"}
    bitacora.registrar(
        accion=accion,
        objeto_tipo="institutos",
        objeto_id="ubicaciones",
        despues={**detalle, "solicitado_por": evento.payload.get("usuario", "")},
    )
