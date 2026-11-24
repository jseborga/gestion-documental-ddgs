import datetime as dt

import pytest
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.auditoria import services as bitacora
from apps.auditoria.models import Bitacora
from apps.core import services as core_services
from apps.core.models import Cargo, Persona, Unidad
from apps.eventos import services as eventos
from apps.eventos.models import EjecucionTarea, EventoOutbox

pytestmark = pytest.mark.django_db


class TestBitacora:
    def test_registrar_y_ocultar_campos_sensibles(self):
        registro = bitacora.registrar(
            accion="prueba", objeto_tipo="x", objeto_id=1, despues={"password": "secreto", "a": 1}
        )
        assert registro.despues == {"password": "***", "a": 1}

    def test_la_base_impide_modificar(self):
        registro = bitacora.registrar(accion="prueba")
        with pytest.raises(DatabaseError), transaction.atomic():
            Bitacora.objects.filter(pk=registro.pk).update(accion="alterada")

    def test_la_base_impide_borrar(self):
        registro = bitacora.registrar(accion="prueba")
        with pytest.raises(DatabaseError), transaction.atomic():
            Bitacora.objects.filter(pk=registro.pk).delete()
        assert Bitacora.objects.filter(pk=registro.pk, accion="prueba").exists()

    def test_actor_anonimo_no_se_guarda(self):
        from django.contrib.auth.models import AnonymousUser

        registro = bitacora.registrar(accion="prueba", actor=AnonymousUser())
        assert registro.actor_id is None and registro.actor_nombre == ""


class TestOutbox:
    def test_publicar_serializa_el_payload(self):
        with transaction.atomic():
            evento = eventos.publicar(
                tipo="t", agregado="a", agregado_id=1, payload={"f": dt.date(2026, 1, 1)}
            )
        assert evento.payload == {"f": "2026-01-01"}

    def test_evento_desaparece_si_la_transaccion_falla(self):
        with pytest.raises(RuntimeError), transaction.atomic():
            eventos.publicar(tipo="t.rollback", agregado="a", agregado_id=1)
            raise RuntimeError("falla de negocio")
        assert not EventoOutbox.objects.filter(tipo="t.rollback").exists()

    def test_procesa_con_consumidor(self):
        recibidos = []

        @eventos.suscribir("prueba.ok")
        def consumidor(evento):
            recibidos.append(evento.agregado_id)

        with transaction.atomic():
            eventos.publicar(tipo="prueba.ok", agregado="a", agregado_id=7)
        assert eventos.procesar_lote() >= 1
        assert "7" in recibidos
        assert EventoOutbox.objects.get(tipo="prueba.ok").procesado_en is not None

    def test_error_del_consumidor_no_detiene_y_se_reintenta(self):
        @eventos.suscribir("prueba.falla")
        def consumidor(evento):
            raise ValueError("sin conexión")

        with transaction.atomic():
            eventos.publicar(tipo="prueba.falla", agregado="a", agregado_id=1)
        for _ in range(eventos.MAX_INTENTOS + 2):
            eventos.procesar_lote()
        evento = EventoOutbox.objects.get(tipo="prueba.falla")
        assert evento.procesado_en is None
        assert evento.intentos == eventos.MAX_INTENTOS
        assert "sin conexión" in evento.ultimo_error

    def test_comando_una_vez(self, capsys):
        call_command("procesar_eventos")
        assert "Eventos procesados" in capsys.readouterr().out


class TestTareasPeriodicas:
    def test_se_ejecuta_una_vez_por_periodo(self):
        llamadas = []

        @eventos.tarea_periodica("tarea_de_prueba", cada=dt.timedelta(hours=1))
        def tarea():
            llamadas.append(1)
            return "hecho"

        ahora = timezone.now()
        assert "tarea_de_prueba" in eventos.ejecutar_tareas_vencidas(ahora)
        assert "tarea_de_prueba" not in eventos.ejecutar_tareas_vencidas(
            ahora + dt.timedelta(minutes=30)
        )
        assert "tarea_de_prueba" in eventos.ejecutar_tareas_vencidas(
            ahora + dt.timedelta(minutes=61)
        )
        assert len(llamadas) == 2
        assert EjecucionTarea.objects.get(nombre="tarea_de_prueba").ultimo_resultado == "hecho"

    def test_error_en_tarea_se_registra(self):
        @eventos.tarea_periodica("tarea_que_falla", cada=dt.timedelta(hours=1))
        def tarea():
            raise OSError("disco lleno")

        eventos.ejecutar_tareas_vencidas()
        assert (
            "disco lleno" in EjecucionTarea.objects.get(nombre="tarea_que_falla").ultimo_resultado
        )


class TestCoreRegistraBitacoraYEventos:
    def test_asignar_cargo(self):
        unidad = Unidad.objects.create(sigla="UX", nombre="U")
        cargo = Cargo.objects.create(unidad=unidad, codigo="UX-1", nombre="C")
        persona = Persona.objects.create(nombres="A", apellidos="B")
        ocupacion = core_services.asignar_cargo(
            persona=persona, cargo=cargo, tipo="titular", desde=dt.date(2026, 1, 1)
        )
        assert Bitacora.objects.filter(
            accion="ocupacion_asignada", objeto_id=str(ocupacion.pk)
        ).exists()
        assert EventoOutbox.objects.filter(
            tipo="core.ocupacion_asignada", agregado_id=str(ocupacion.pk)
        ).exists()
        core_services.terminar_ocupacion(ocupacion=ocupacion, hasta=dt.date(2026, 2, 1))
        registro = Bitacora.objects.get(accion="ocupacion_terminada")
        assert registro.antes == {"hasta": None} and registro.despues == {"hasta": "2026-02-01"}


@pytest.mark.django_db(transaction=True)
def test_migraciones_de_auditoria_y_eventos_son_reversibles():
    call_command("migrate", "auditoria", "zero", verbosity=0)
    call_command("migrate", "eventos", "zero", verbosity=0)
    call_command("migrate", verbosity=0)


@pytest.mark.django_db(transaction=True)
def test_publicar_fuera_de_transaccion_se_rechaza():
    with pytest.raises(RuntimeError):
        eventos.publicar(tipo="t", agregado="a", agregado_id=1)
