import tempfile
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.auditoria.models import Bitacora
from apps.eventos import services as eventos
from apps.eventos.models import EventoOutbox
from apps.institutos import geocodificacion
from apps.institutos.models import Instituto, ObservacionDato, Precision

from .conftest import verificar_cliente
from .institutos_util import instituto, unidad_con_cargos, usuario_con_cargo
from .planillas_sinteticas import crear_datos, crear_ficha

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def patrones(settings):
    settings.INSTITUTOS_TITULAR_PATRONES = ["gobierno autonomo"]


@pytest.fixture
def admin(client):
    usuario = User.objects.create_user("adm", password="Clave-larga-de-prueba-2026")
    usuario.groups.add(Group.objects.get(name="administrador"))
    return verificar_cliente(client, User.objects.get(pk=usuario.pk))


@pytest.fixture
def archivos(tmp_path):
    def subir(ruta):
        return SimpleUploadedFile(ruta.name, ruta.read_bytes())

    datos = crear_datos(tmp_path / "datos.xlsx")
    ficha = crear_ficha(tmp_path / "ficha.xlsx")
    return lambda: {"datos": subir(datos), "ficha": subir(ficha)}


@pytest.fixture
def unidad():
    return unidad_con_cargos()[0]


def test_solo_administrador(client, unidad, archivos):
    tecnico = usuario_con_cargo("tec", "tecnico", unidad.cargos.get(codigo="DDGS-TEC"))
    verificar_cliente(client, tecnico)
    assert client.get("/institutos/importar/").status_code == 403
    respuesta = client.post("/institutos/importar/", {"unidad": unidad.pk, **archivos()})
    assert respuesta.status_code == 403
    assert client.post("/institutos/aproximar/").status_code == 403
    assert not Instituto.objects.exists()


def test_anonimo_redirige(client):
    assert client.get("/institutos/importar/").status_code == 302


def test_simular_y_luego_importar(admin, unidad, archivos):
    respuesta = admin.post(
        "/institutos/importar/", {"unidad": unidad.pk, "simular": "on", **archivos()}
    )
    html = respuesta.content.decode()
    assert respuesta.status_code == 200 and "SIMULACIÓN" in html and "Folio real" in html
    assert not Instituto.objects.exists()
    respuesta = admin.post("/institutos/importar/", {"unidad": unidad.pk, **archivos()})
    assert "Importación aplicada" in respuesta.content.decode()
    assert Instituto.objects.count() == 3
    registro = Bitacora.objects.get(accion="institutos_importados")
    assert registro.actor_nombre == "adm"


def test_observaciones_csv(admin, unidad, archivos):
    csv = SimpleUploadedFile("obs.csv", "1;Revisar dirección\n".encode())
    admin.post("/institutos/importar/", {"unidad": unidad.pk, "observaciones": csv, **archivos()})
    assert ObservacionDato.objects.filter(texto="Revisar dirección").exists()


@pytest.mark.parametrize(
    ("nombre", "contenido", "mensaje"),
    [
        ("datos.xls", b"x", "Debe ser un archivo .xlsx"),
        ("datos.xlsx", b"<html>no es excel</html>", "no es un libro de Excel"),
        ("../../etc/passwd.xlsx", b"PK\x03\x04basura", "archivo da"),
    ],
)
def test_archivos_rechazados(admin, unidad, archivos, nombre, contenido, mensaje):
    datos = {"unidad": unidad.pk, **archivos()}
    datos["datos"] = SimpleUploadedFile(nombre, contenido)
    html = admin.post("/institutos/importar/", datos).content.decode()
    assert mensaje in html
    assert not Instituto.objects.exists()


def test_tamano_maximo(admin, unidad, archivos, settings):
    settings.IMPORTACION_MAX_MB = 0
    html = admin.post("/institutos/importar/", {"unidad": unidad.pk, **archivos()}).content.decode()
    assert "tamaño máximo" in html


def test_no_quedan_archivos_temporales(admin, unidad, archivos):
    antes = set(Path(tempfile.gettempdir()).glob("importacion-*"))
    admin.post("/institutos/importar/", {"unidad": unidad.pk, "simular": "on", **archivos()})
    assert set(Path(tempfile.gettempdir()).glob("importacion-*")) == antes


def test_error_inesperado_no_filtra_detalles(admin, unidad, archivos, monkeypatch):
    from apps.institutos import importador

    def falla(*args, **kwargs):
        raise RuntimeError("detalle interno secreto")

    monkeypatch.setattr(importador, "leer", falla)
    html = admin.post("/institutos/importar/", {"unidad": unidad.pk, **archivos()}).content.decode()
    assert "No se pudo procesar el archivo" in html and "secreto" not in html


class TestAproximacionEnSegundoPlano:
    def test_solicitud_y_procesamiento(self, admin, unidad, settings, monkeypatch):
        settings.NOMINATIM_CONTACTO = "soporte@ejemplo.invalid"
        monkeypatch.setattr(
            geocodificacion, "_consultar", lambda p: [{"lat": "-16.40", "lon": "-68.30"}]
        )
        monkeypatch.setattr(geocodificacion, "pausa", lambda: None)
        inst = instituto(unidad, 1, "Uno", municipio="Municipio A")
        assert admin.post("/institutos/aproximar/").status_code == 302
        assert admin.post("/institutos/aproximar/", follow=True).status_code == 200  # duplicada
        assert EventoOutbox.objects.filter(tipo="institutos.aproximar_solicitado").count() == 1
        eventos.procesar_lote()
        inst.refresh_from_db()
        assert inst.precision == Precision.APROXIMADA
        resultado = Bitacora.objects.get(accion="ubicaciones_aproximadas")
        assert "1 ubicados" in resultado.despues["resumen"]
        assert "aproximada" in admin.get("/institutos/importar/").content.decode().lower()

    def test_sin_contacto_registra_error_sin_reintentar(self, admin, unidad, settings):
        settings.NOMINATIM_CONTACTO = ""
        instituto(unidad, 1, "Uno", municipio="Municipio A")
        admin.post("/institutos/aproximar/")
        eventos.procesar_lote()
        evento = EventoOutbox.objects.get(tipo="institutos.aproximar_solicitado")
        assert evento.procesado_en is not None  # no se reintenta un error de configuración
        assert Bitacora.objects.filter(accion="ubicaciones_aproximadas_error").exists()
