import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.core import selectors, services
from apps.core.models import Cargo, Feriado, OcupacionCargo, Persona, Unidad

pytestmark = pytest.mark.django_db

D = dt.date


@pytest.fixture
def unidad():
    return Unidad.objects.create(sigla="UPRUEBA", nombre="Unidad de prueba", prefijo_cite="X/UP")


@pytest.fixture
def director(unidad):
    return Cargo.objects.create(
        unidad=unidad, codigo="UP-DIR", nombre="Director", puede_firmar=True
    )


@pytest.fixture
def tecnico(unidad):
    return Cargo.objects.create(unidad=unidad, codigo="UP-TEC", nombre="Técnico")


def persona(nombre: str) -> Persona:
    return Persona.objects.create(nombres=nombre, apellidos="Prueba")


class TestCargosVigentes:
    def test_titular_vigente_desde_su_fecha(self, director):
        ana = persona("Ana")
        services.asignar_cargo(persona=ana, cargo=director, tipo="titular", desde=D(2026, 1, 5))
        assert list(selectors.cargos_vigentes(ana, D(2026, 1, 5))) == [director]
        assert list(selectors.cargos_vigentes(ana, D(2026, 1, 4))) == []

    def test_suplencia_aparece_y_desaparece_con_sus_fechas(self, director, tecnico):
        titular, suplente = persona("Titular"), persona("Suplente")
        services.asignar_cargo(persona=titular, cargo=director, tipo="titular", desde=D(2026, 1, 1))
        services.asignar_cargo(persona=suplente, cargo=tecnico, tipo="titular", desde=D(2026, 1, 1))
        services.asignar_cargo(
            persona=suplente,
            cargo=director,
            tipo="suplente",
            desde=D(2026, 7, 1),
            hasta=D(2026, 7, 15),
        )
        antes = set(selectors.cargos_vigentes(suplente, D(2026, 6, 30)))
        durante = set(selectors.cargos_vigentes(suplente, D(2026, 7, 15)))
        despues = set(selectors.cargos_vigentes(suplente, D(2026, 7, 16)))
        assert antes == {tecnico}
        assert durante == {tecnico, director}
        assert despues == {tecnico}
        # El titular conserva su cargo durante la suplencia.
        assert set(selectors.cargos_vigentes(titular, D(2026, 7, 10))) == {director}

    def test_ocupacion_terminada_deja_de_estar_vigente(self, director):
        ana = persona("Ana")
        ocupacion = services.asignar_cargo(
            persona=ana, cargo=director, tipo="titular", desde=D(2026, 1, 1)
        )
        services.terminar_ocupacion(ocupacion=ocupacion, hasta=D(2026, 3, 31))
        assert list(selectors.cargos_vigentes(ana, D(2026, 3, 31))) == [director]
        assert list(selectors.cargos_vigentes(ana, D(2026, 4, 1))) == []

    def test_cargo_inactivo_no_cuenta(self, director):
        ana = persona("Ana")
        services.asignar_cargo(persona=ana, cargo=director, tipo="titular", desde=D(2026, 1, 1))
        Cargo.objects.filter(pk=director.pk).update(activo=False)
        assert list(selectors.cargos_vigentes(ana, D(2026, 2, 1))) == []


class TestAsignarCargo:
    def test_rechaza_dos_titulares_que_se_solapan(self, director):
        services.asignar_cargo(
            persona=persona("A"),
            cargo=director,
            tipo="titular",
            desde=D(2026, 1, 1),
            hasta=D(2026, 6, 30),
        )
        with pytest.raises(ValidationError):
            services.asignar_cargo(
                persona=persona("B"), cargo=director, tipo="titular", desde=D(2026, 6, 30)
            )

    def test_permite_titular_siguiente_sin_solape(self, director):
        services.asignar_cargo(
            persona=persona("A"),
            cargo=director,
            tipo="titular",
            desde=D(2026, 1, 1),
            hasta=D(2026, 6, 30),
        )
        nueva = services.asignar_cargo(
            persona=persona("B"), cargo=director, tipo="titular", desde=D(2026, 7, 1)
        )
        assert nueva.pk is not None

    def test_permite_interino_junto_al_titular(self, director):
        services.asignar_cargo(
            persona=persona("A"), cargo=director, tipo="titular", desde=D(2026, 1, 1)
        )
        interino = services.asignar_cargo(
            persona=persona("B"), cargo=director, tipo="interino", desde=D(2026, 2, 1)
        )
        assert interino.tipo == OcupacionCargo.Tipo.INTERINO

    def test_rechaza_fechas_invertidas(self, director):
        with pytest.raises(ValidationError):
            services.asignar_cargo(
                persona=persona("A"),
                cargo=director,
                tipo="titular",
                desde=D(2026, 5, 1),
                hasta=D(2026, 4, 1),
            )

    def test_rechaza_persona_inactiva(self, director):
        inactiva = Persona.objects.create(nombres="X", apellidos="Y", activo=False)
        with pytest.raises(ValidationError):
            services.asignar_cargo(
                persona=inactiva, cargo=director, tipo="titular", desde=D(2026, 1, 1)
            )

    def test_la_base_impide_dos_titulares_abiertos(self, director):
        OcupacionCargo.objects.create(
            persona=persona("A"), cargo=director, tipo="titular", desde=D(2026, 1, 1)
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            OcupacionCargo.objects.create(
                persona=persona("B"), cargo=director, tipo="titular", desde=D(2026, 2, 1)
            )

    def test_no_se_puede_cerrar_antes_del_inicio(self, director):
        ocupacion = services.asignar_cargo(
            persona=persona("A"), cargo=director, tipo="titular", desde=D(2026, 3, 1)
        )
        with pytest.raises(ValidationError):
            services.terminar_ocupacion(ocupacion=ocupacion, hasta=D(2026, 2, 28))


class TestDiasHabiles:
    def test_salta_fin_de_semana(self):
        viernes = D(2026, 11, 20)
        assert selectors.sumar_dias_habiles(viernes, 1) == D(2026, 11, 23)  # lunes

    def test_salta_feriados_registrados(self):
        Feriado.objects.create(fecha=D(2026, 11, 23), nombre="Feriado de prueba", ambito="nacional")
        assert selectors.sumar_dias_habiles(D(2026, 11, 20), 1) == D(2026, 11, 24)
        assert not selectors.es_dia_habil(D(2026, 11, 23))

    def test_cinco_dias_habiles(self):
        lunes = D(2026, 11, 23)
        assert selectors.sumar_dias_habiles(lunes, 5) == D(2026, 11, 30)

    def test_cero_dias_y_negativos(self):
        assert selectors.sumar_dias_habiles(D(2026, 11, 22), 0) == D(2026, 11, 22)
        with pytest.raises(ValueError):
            selectors.sumar_dias_habiles(D(2026, 11, 22), -1)


class TestSemillas:
    def test_carga_idempotente(self):
        call_command("cargar_semillas")
        conteo = (
            Unidad.objects.count(),
            Cargo.objects.count(),
            Persona.objects.count(),
            OcupacionCargo.objects.count(),
        )
        call_command("cargar_semillas")
        assert conteo == (
            Unidad.objects.count(),
            Cargo.objects.count(),
            Persona.objects.count(),
            OcupacionCargo.objects.count(),
        )
        assert Unidad.objects.get(sigla="DDGS").padre.sigla == "SDGS"

    def test_semillas_son_sinteticas(self):
        call_command("cargar_semillas")
        assert all(p.email.endswith("@ejemplo.invalid") for p in Persona.objects.all()), (
            "Las semillas solo pueden contener personas ficticias"
        )

    def test_suplencia_semilla_da_bandeja_de_director(self):
        call_command("cargar_semillas")
        fiscal = Persona.objects.get(email="diego.ejemplo@ejemplo.invalid")
        codigos = {c.codigo for c in selectors.cargos_vigentes(fiscal, D(2026, 7, 10))}
        assert codigos == {"DDGS-FISCAL-1", "DDGS-DIRECTOR"}


def test_semillas_solo_estructura_sin_datos_ficticios():
    from apps.core.models import InstitucionExterna, Proceso, Proyecto

    call_command("cargar_semillas", "--solo-estructura")
    assert Unidad.objects.filter(sigla="DDGS").exists()
    assert Cargo.objects.filter(codigo="DDGS-DIRECTOR").exists()
    assert Proceso.objects.count() == 8
    assert not Persona.objects.exists()
    assert not OcupacionCargo.objects.exists()
    assert not InstitucionExterna.objects.exists()
    assert not Proyecto.objects.exists()
