"""Almacenamiento privado de archivos.

El almacenamiento S3 (SeaweedFS) solo es accesible por la red interna de Docker: el
navegador nunca recibe su URL. Los archivos se entregan siempre a través de una vista
del backend que verifica permisos con `puede()` y transmite el contenido (proxy).
Por eso `url()` está bloqueado: cualquier intento de generar un enlace directo falla
en vez de filtrar la dirección interna.
"""

from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage

MENSAJE = (
    "Los archivos no tienen URL directa: se descargan por el backend, que verifica "
    "permisos y transmite el contenido."
)


class SinUrlDirecta:
    def url(self, name, *args, **kwargs):
        raise NotImplementedError(MENSAJE)


class AlmacenPrivadoS3(SinUrlDirecta, S3Storage):
    """S3 interno (SeaweedFS) por HTTP en la red de Docker, estilo de ruta."""


class AlmacenPrivadoLocal(SinUrlDirecta, FileSystemStorage):
    """Disco local (desarrollo y pruebas) con la misma regla."""
