from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command

from apps.archivos.almacen import AlmacenPrivadoS3
from apps.archivos.management.commands import preparar_almacenamiento as comando


def test_almacen_local_no_entrega_url_directa():
    nombre = default_storage.save("prueba/archivo.txt", ContentFile(b"hola"))
    assert default_storage.exists(nombre)
    with pytest.raises(NotImplementedError, match="se descargan por el backend"):
        default_storage.url(nombre)


def test_almacen_s3_no_entrega_url_interna():
    almacen = AlmacenPrivadoS3(
        endpoint_url="http://proyecto_seaweedfs:8333",
        access_key="x",
        secret_key="y",
        bucket_name="documentos",
        addressing_style="path",
    )
    with pytest.raises(NotImplementedError):
        almacen.url("documentos/1.pdf")


class ClienteFalso:
    def __init__(self, existe=True, codigo="404", crear_falla=False, conexion_falla=False):
        self.existe, self.codigo = existe, codigo
        self.crear_falla, self.conexion_falla = crear_falla, conexion_falla
        self.creado = None

    def head_bucket(self, Bucket):
        if self.conexion_falla:
            raise EndpointConnectionError(endpoint_url="http://proyecto_seaweedfs:8333")
        if not self.existe:
            raise ClientError({"Error": {"Code": self.codigo}}, "HeadBucket")

    def create_bucket(self, Bucket):
        if self.crear_falla:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "CreateBucket")
        self.creado = Bucket


@pytest.fixture
def con_s3(settings, monkeypatch):
    settings.S3_ENDPOINT = "http://proyecto_seaweedfs:8333"
    settings.STORAGES = {**settings.STORAGES, "default": {"OPTIONS": {"bucket_name": "documentos"}}}

    def usar(cliente):
        almacen = SimpleNamespace(connection=SimpleNamespace(meta=SimpleNamespace(client=cliente)))
        monkeypatch.setattr(comando, "default_storage", almacen)
        return cliente

    return usar


def test_local_no_hace_nada(settings, capsys):
    settings.S3_ENDPOINT = ""
    call_command("preparar_almacenamiento")
    assert "nada que preparar" in capsys.readouterr().out


def test_bucket_existente(con_s3, capsys):
    con_s3(ClienteFalso(existe=True))
    call_command("preparar_almacenamiento")
    assert "disponible" in capsys.readouterr().out


def test_crea_bucket_faltante(con_s3):
    cliente = con_s3(ClienteFalso(existe=False))
    call_command("preparar_almacenamiento")
    assert cliente.creado == "documentos"


def test_credenciales_sin_permiso(con_s3):
    con_s3(ClienteFalso(existe=False, codigo="403"))
    with pytest.raises(CommandError, match="S3_ACCESS_KEY"):
        call_command("preparar_almacenamiento")


def test_no_puede_crear(con_s3):
    con_s3(ClienteFalso(existe=False, crear_falla=True))
    with pytest.raises(CommandError, match="no se pudo crear"):
        call_command("preparar_almacenamiento")


def test_sin_conexion_indica_red(con_s3):
    con_s3(ClienteFalso(conexion_falla=True))
    with pytest.raises(CommandError, match="misma red de Docker"):
        call_command("preparar_almacenamiento")


def test_host_con_guion_bajo_detiene_el_arranque_con_mensaje_claro():
    import os
    import subprocess
    import sys

    entorno = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.dev",
        "DJANGO_SECRET_KEY": "x",
        "S3_ENDPOINT": "http://estudio_seaweedfs:8333",
    }
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import django; django.setup()"],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0
    assert "s3-proxy" in resultado.stderr and "guion bajo" in resultado.stderr
