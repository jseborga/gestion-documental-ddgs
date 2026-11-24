import datetime as dt

import pytest
from django.core.management import call_command

from apps.core.models import Cargo, OcupacionCargo, Persona, Unidad


@pytest.fixture
def datos(db):
    unidad = Unidad.objects.create(sigla="UA", nombre="Unidad A")
    cargo = Cargo.objects.create(unidad=unidad, codigo="UA-DIR", nombre="Director")
    a = Persona.objects.create(nombres="A", apellidos="Uno")
    b = Persona.objects.create(nombres="B", apellidos="Dos")
    return cargo, a, b


def _post(admin_client, cargo, persona, desde, tipo="titular"):
    return admin_client.post(
        "/admin/core/ocupacioncargo/add/",
        {
            "persona": persona.pk,
            "cargo": cargo.pk,
            "tipo": tipo,
            "desde": desde,
            "hasta": "",
            "acto_designacion": "Memo de prueba",
        },
    )


def test_admin_crea_ocupacion_por_el_servicio(admin_client, datos):
    cargo, a, _ = datos
    respuesta = _post(admin_client, cargo, a, "2026-01-01")
    assert respuesta.status_code == 302
    assert OcupacionCargo.objects.filter(cargo=cargo, persona=a).count() == 1


def test_admin_rechaza_titular_solapado(admin_client, datos):
    cargo, a, b = datos
    _post(admin_client, cargo, a, "2026-01-01")
    respuesta = _post(admin_client, cargo, b, "2026-02-01")
    assert respuesta.status_code == 200  # vuelve al formulario con error
    assert "ya tiene un titular" in respuesta.content.decode()
    assert OcupacionCargo.objects.filter(cargo=cargo).count() == 1


def test_admin_cierra_ocupacion(admin_client, datos):
    cargo, a, _ = datos
    _post(admin_client, cargo, a, "2026-01-01")
    ocupacion = OcupacionCargo.objects.get(cargo=cargo)
    respuesta = admin_client.post(
        f"/admin/core/ocupacioncargo/{ocupacion.pk}/change/", {"hasta": "2026-03-31"}
    )
    assert respuesta.status_code == 302
    ocupacion.refresh_from_db()
    assert ocupacion.hasta == dt.date(2026, 3, 31)


def test_admin_no_permite_borrar_ocupaciones(admin_client, datos):
    cargo, a, _ = datos
    _post(admin_client, cargo, a, "2026-01-01")
    ocupacion = OcupacionCargo.objects.get(cargo=cargo)
    respuesta = admin_client.get(f"/admin/core/ocupacioncargo/{ocupacion.pk}/delete/")
    assert respuesta.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_migraciones_de_core_son_reversibles():
    call_command("migrate", "core", "zero", verbosity=0)
    call_command("migrate", "core", verbosity=0)
