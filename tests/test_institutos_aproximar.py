from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command

from apps.institutos import geocodificacion
from apps.institutos.models import Instituto, Precision

from .institutos_util import instituto, unidad_con_cargos

pytestmark = pytest.mark.django_db


@pytest.fixture
def sin_red(monkeypatch, settings):
    settings.NOMINATIM_CONTACTO = "soporte@ejemplo.invalid"
    llamadas = []
    respuestas = {
        "Municipio A": [{"lat": "-16.40", "lon": "-68.30"}],
        "Municipio Lejano": [{"lat": "-33.0", "lon": "-70.5"}],  # fuera de zona
        "Municipio Inexistente": [],
    }

    def falso(parametros):
        llamadas.append(parametros)
        return respuestas[parametros["q"].split(",")[0]]

    monkeypatch.setattr(geocodificacion, "_consultar", falso)
    monkeypatch.setattr(geocodificacion, "pausa", lambda: None)
    return llamadas


def test_ubica_aproximado_con_cache_y_descarta_fuera_de_zona(sin_red, capsys):
    unidad, _ = unidad_con_cargos()
    a1 = instituto(unidad, 1, "Uno", municipio="Municipio A")
    a2 = instituto(unidad, 2, "Dos", municipio="Municipio A")
    lejano = instituto(unidad, 3, "Tres", municipio="Municipio Lejano")
    nada = instituto(unidad, 4, "Cuatro", municipio="Municipio Inexistente")
    call_command("aproximar_ubicaciones")
    assert len(sin_red) == 3  # Municipio A se consulta una sola vez
    for inst in (a1, a2):
        inst.refresh_from_db()
        assert (inst.lat, inst.precision) == (Decimal("-16.400000"), Precision.APROXIMADA)
        assert "aproximada" in inst.ubicaciones.first().fuente.lower()
    lejano.refresh_from_db()
    nada.refresh_from_db()
    assert lejano.lat is None and nada.lat is None
    assert "1 fuera de zona" in capsys.readouterr().out


def test_simulacion_no_guarda(sin_red):
    unidad, _ = unidad_con_cargos()
    instituto(unidad, 1, "Uno", municipio="Municipio A")
    call_command("aproximar_ubicaciones", "--simular")
    assert not Instituto.objects.filter(lat__isnull=False).exists()


def test_exige_contacto(settings):
    settings.NOMINATIM_CONTACTO = ""
    unidad, _ = unidad_con_cargos()
    instituto(unidad, 1, "Uno", municipio="Municipio A")
    with pytest.raises(CommandError, match="NOMINATIM_CONTACTO"):
        call_command("aproximar_ubicaciones")


def test_no_toca_institutos_ya_ubicados(sin_red):
    unidad, _ = unidad_con_cargos()
    instituto(unidad, 1, "Uno", municipio="Municipio A", lat=Decimal("-16.5"), lon=Decimal("-68.1"),
              precision=Precision.GPS_SITIO)  # fmt: skip
    call_command("aproximar_ubicaciones")
    assert sin_red == []
