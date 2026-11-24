from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.auditoria.models import Bitacora
from apps.eventos.models import EventoOutbox
from apps.institutos import services
from apps.institutos.models import Matricula, ObservacionDato, Precision
from apps.seguridad.permisos import Accion, puede

from .institutos_util import instituto, unidad_con_cargos, usuario_con_cargo

pytestmark = pytest.mark.django_db


class TestParsearCoordenadas:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("-16.5000, -68.1500", ("-16.5000", "-68.1500")),
            ("-16,5 ; -68,15", ("-16.5", "-68.15")),
            ("https://www.google.com/maps/@-16.4955,-68.1336,15z", ("-16.4955", "-68.1336")),
            (
                "https://www.google.com/maps/place/X/@-16.49,-68.13,17z/data=!3d-16.4951!4d-68.1337",
                ("-16.49", "-68.13"),
            ),
            ("https://www.google.com/maps/search/?api=1&query=-17.0,-67.5", ("-17.0", "-67.5")),
        ],
    )
    def test_formatos_validos(self, texto, esperado):
        lat, lon = services.parsear_coordenadas(texto)
        assert (lat, lon) == (Decimal(esperado[0]), Decimal(esperado[1]))

    @pytest.mark.parametrize(
        "texto",
        ["", "La Paz", "https://maps.app.goo.gl/abc123", "https://goo.gl/maps/xyz", "abc,def"],
    )
    def test_rechaza(self, texto):
        with pytest.raises(ValidationError):
            services.parsear_coordenadas(texto)


class TestRegistrarUbicacion:
    def test_registra_historial_copia_y_bitacora(self):
        unidad, _ = unidad_con_cargos()
        inst = instituto(unidad)
        services.registrar_ubicacion(
            instituto=inst,
            lat=Decimal("-16.5"),
            lon=Decimal("-68.15"),
            precision=Precision.VERIFICADA_MAPA,
            fuente="Google Maps",
        )
        services.registrar_ubicacion(
            instituto=inst,
            lat=Decimal("-16.51"),
            lon=Decimal("-68.16"),
            precision=Precision.GPS_SITIO,
            fuente="Visita",
        )
        inst.refresh_from_db()
        assert inst.ubicaciones.count() == 2
        assert (inst.lat, inst.lon, inst.precision) == (
            Decimal("-16.510000"),
            Decimal("-68.160000"),
            Precision.GPS_SITIO,
        )
        assert Bitacora.objects.filter(accion="ubicacion_registrada").count() == 2
        assert EventoOutbox.objects.filter(tipo="institutos.ubicacion_registrada").count() == 2

    @pytest.mark.parametrize(
        ("lat", "lon"),
        [("-68.15", "-16.5"), ("16.5", "-68.15"), ("-16.5", "68.15"), ("-25.0", "-65.0")],
    )
    def test_fuera_de_zona(self, lat, lon):
        unidad, _ = unidad_con_cargos()
        with pytest.raises(ValidationError):
            services.registrar_ubicacion(
                instituto=instituto(unidad),
                lat=Decimal(lat),
                lon=Decimal(lon),
                precision=Precision.VERIFICADA_MAPA,
            )

    def test_precision_pendiente_no_se_acepta(self):
        unidad, _ = unidad_con_cargos()
        with pytest.raises(ValidationError):
            services.registrar_ubicacion(
                instituto=instituto(unidad),
                lat=Decimal("-16.5"),
                lon=Decimal("-68.1"),
                precision=Precision.PENDIENTE,
            )


class TestRestricciones:
    def test_matricula_sin_mes_no_se_duplica(self):
        unidad, _ = unidad_con_cargos()
        inst = instituto(unidad)
        Matricula.objects.create(instituto=inst, anio=2026, estudiantes=100, fuente="x")
        with pytest.raises(IntegrityError), transaction.atomic():
            Matricula.objects.create(instituto=inst, anio=2026, estudiantes=120, fuente="x")

    def test_observacion_general_no_se_duplica(self):
        ObservacionDato.objects.create(texto="general", origen="importacion")
        with pytest.raises(IntegrityError), transaction.atomic():
            ObservacionDato.objects.create(texto="general", origen="importacion")


class TestPermisosSobreInstituto:
    def test_matriz(self):
        unidad, cargos = unidad_con_cargos()
        otra, cargos_otra = unidad_con_cargos("OTRA")
        inst = instituto(unidad)
        director = usuario_con_cargo("dir", "director", cargos["dir"])
        tecnico = usuario_con_cargo("tec", "tecnico", cargos["tec"])
        ventanilla = usuario_con_cargo("ven", "ventanilla", cargos["ven"])
        externo = usuario_con_cargo("ext", "tecnico", cargos_otra["tec"])
        auditor = usuario_con_cargo("aud", "auditor", None)
        assert [
            puede(u, Accion.VER, inst) for u in (director, tecnico, ventanilla, externo, auditor)
        ] == [
            True,
            True,
            True,
            False,
            True,
        ]
        assert [
            puede(u, Accion.EDITAR, inst) for u in (director, tecnico, ventanilla, externo, auditor)
        ] == [
            True,
            True,
            False,
            False,
            False,
        ]


def test_expresion_de_coordenadas_sin_retroceso_costoso():
    import time

    texto = "1" + " " * 1900 + "x"
    inicio = time.perf_counter()
    with pytest.raises(ValidationError):
        services.parsear_coordenadas(texto)
    assert time.perf_counter() - inicio < 0.05
