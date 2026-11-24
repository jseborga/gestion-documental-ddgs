import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_salud_responde_ok(client):
    respuesta = client.get("/api/v1/salud/")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "ok"
    assert datos["base_de_datos"] == "ok"
    assert datos["almacenamiento"] == "ok"


def test_salud_503_si_falla_el_almacenamiento(client, monkeypatch):
    from apps.api import views

    def falla(*args, **kwargs):
        raise OSError("sin conexión")

    monkeypatch.setattr(views.default_storage, "exists", falla)
    respuesta = client.get("/api/v1/salud/")
    assert respuesta.status_code == 503
    datos = respuesta.json()
    assert datos["almacenamiento"] == "error"
    assert "sin conexión" not in respuesta.content.decode()  # no filtra detalles internos


def test_salud_solo_get(client):
    assert client.post("/api/v1/salud/").status_code == 405


def test_procesar_eventos_una_vez(capsys):
    call_command("procesar_eventos")
    assert "Eventos procesados: 0" in capsys.readouterr().out


def test_no_hay_migraciones_pendientes():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
