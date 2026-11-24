import datetime as dt
import time

import pytest
from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import RequestFactory, override_settings
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.auditoria import services as bitacora
from apps.auditoria.models import Bitacora
from apps.core import services as core_services
from apps.core.models import Cargo, Persona, Unidad
from apps.seguridad import services, tareas
from apps.seguridad.models import SesionUsuario
from apps.seguridad.red import ip_cliente

from .conftest import verificar_cliente

pytestmark = pytest.mark.django_db
CLAVE = "Clave-de-prueba-larga-2026"


def usuario(nombre="ana", rol=None, **extra):
    u = User.objects.create_user(nombre, password=CLAVE, **extra)
    if rol:
        u.groups.add(Group.objects.get(name=rol))
    return User.objects.get(pk=u.pk)


def entrar(client, nombre, clave=CLAVE):
    return client.post("/seguridad/entrar/", {"username": nombre, "password": clave})


def codigo_actual(dispositivo):
    valor = totp(
        dispositivo.bin_key, step=dispositivo.step, t0=dispositivo.t0, digits=dispositivo.digits
    )
    return f"{valor:06d}"


class TestInicioDeSesion:
    def test_inicio_correcto_registra_bitacora_y_sesion(self, client):
        u = usuario(rol="tecnico")
        respuesta = entrar(client, "ana")
        assert respuesta.status_code == 302
        assert Bitacora.objects.filter(accion="inicio_sesion", actor=u).exists()
        assert SesionUsuario.objects.filter(usuario=u).count() == 1

    def test_paginas_exigen_sesion(self, client):
        respuesta = client.get("/")
        assert respuesta.status_code == 302 and "/seguridad/entrar/" in respuesta["Location"]

    def test_bloqueo_tras_cinco_fallos(self, client):
        usuario(rol="tecnico")
        for _ in range(5):
            entrar(client, "ana", "incorrecta")
        respuesta = entrar(client, "ana")  # aun con la clave correcta
        assert respuesta.status_code == 429
        assert Bitacora.objects.filter(accion="cuenta_bloqueada_por_intentos").exists()
        assert Bitacora.objects.filter(accion="inicio_sesion_fallido").count() >= 5

    @override_settings(ALERTAS_EMAIL=["admin@ejemplo.invalid"], AXES_FAILURE_LIMIT=100)
    def test_alerta_por_muchos_fallos(self, client):
        for i in range(10):
            entrar(client, f"desconocido{i}", "x")
        assert any("intentos fallidos" in m.subject for m in mail.outbox)
        assert Bitacora.objects.filter(accion="alerta_fallos_sesion").count() == 1

    @override_settings(ALERTAS_EMAIL=["admin@ejemplo.invalid"])
    def test_alerta_por_superusuario(self, client):
        User.objects.create_superuser("raiz", password=CLAVE)
        entrar(client, "raiz")
        assert any("superusuario" in m.subject for m in mail.outbox)
        assert Bitacora.objects.filter(accion="uso_superusuario").exists()

    def test_admin_login_redirige_al_inicio_propio(self, client):
        respuesta = client.get("/admin/login/?next=/admin/")
        assert respuesta.status_code == 302 and respuesta["Location"].startswith(
            "/seguridad/entrar/"
        )


class TestSegundoFactor:
    def test_rol_obligatorio_sin_dispositivo_va_a_configurar(self, client):
        usuario("dir", rol="director")
        entrar(client, "dir")
        respuesta = client.get("/")
        assert (
            respuesta.status_code == 302 and "/seguridad/2fa/configurar/" in respuesta["Location"]
        )

    def test_api_responde_403_sin_segundo_factor(self, client):
        usuario("dir", rol="director")
        entrar(client, "dir")
        respuesta = client.get("/api/v1/esquema/")
        assert respuesta.status_code == 403

    def test_configurar_confirmar_y_codigos(self, client):
        u = usuario("dir", rol="director")
        entrar(client, "dir")
        assert client.get("/seguridad/2fa/configurar/").status_code == 200
        dispositivo = TOTPDevice.objects.get(user=u, confirmed=False)
        respuesta = client.post(
            "/seguridad/2fa/configurar/", {"codigo": codigo_actual(dispositivo)}
        )
        assert respuesta.status_code == 200
        assert len(respuesta.context["codigos"]) == services.CANTIDAD_CODIGOS_RECUPERACION
        assert client.get("/").status_code == 200  # ya verificado
        assert Bitacora.objects.filter(accion="segundo_factor_activado", actor=u).exists()

    def test_codigo_incorrecto_no_confirma(self, client):
        u = usuario("dir", rol="director")
        entrar(client, "dir")
        client.get("/seguridad/2fa/configurar/")
        client.post("/seguridad/2fa/configurar/", {"codigo": "000000"})
        assert not TOTPDevice.objects.filter(user=u, confirmed=True).exists()

    def test_verificar_con_totp_y_con_codigo_de_recuperacion(self, client):
        u = usuario("dir", rol="director")
        dispositivo = TOTPDevice.objects.create(user=u, name="cel", confirmed=True)
        codigos = services.generar_codigos_recuperacion(u)
        entrar(client, "dir")
        assert "/2fa/verificar/" in client.get("/")["Location"]
        client.post("/seguridad/2fa/verificar/", {"codigo": "123"})
        assert Bitacora.objects.filter(accion="segundo_factor_fallido").exists()
        # django-otp impone una espera creciente tras cada fallo; la prueba no espera.
        dispositivo.refresh_from_db()
        assert dispositivo.throttling_failure_count == 1
        dispositivo.throttle_reset()
        from django_otp.plugins.otp_static.models import StaticDevice

        StaticDevice.objects.get(user=u).throttle_reset()
        respuesta = client.post("/seguridad/2fa/verificar/", {"codigo": codigo_actual(dispositivo)})
        assert respuesta.status_code == 302
        assert client.get("/").status_code == 200
        # Otra sesión con un código de recuperación de un solo uso.
        otro = client.__class__()
        entrar(otro, "dir")
        otro.post("/seguridad/2fa/verificar/", {"codigo": codigos[0]})
        assert otro.get("/").status_code == 200
        tercero = client.__class__()
        entrar(tercero, "dir")
        tercero.post("/seguridad/2fa/verificar/", {"codigo": codigos[0]})  # ya usado
        assert tercero.get("/").status_code == 302

    def test_rol_opcional_entra_sin_segundo_factor(self, client):
        usuario(rol="tecnico")
        entrar(client, "ana")
        assert client.get("/").status_code == 200

    def test_redireccion_externa_bloqueada(self, client):
        u = usuario("dir", rol="director")
        dispositivo = TOTPDevice.objects.create(user=u, name="cel", confirmed=True)
        entrar(client, "dir")
        respuesta = client.post(
            "/seguridad/2fa/verificar/",
            {"codigo": codigo_actual(dispositivo), "next": "https://malicioso.example/"},
        )
        assert respuesta["Location"] == "/"


class TestSesiones:
    def test_sesion_maxima_absoluta(self, client):
        usuario(rol="tecnico")
        entrar(client, "ana")
        sesion = client.session
        sesion["inicio_sesion"] = time.time() - 11 * 3600
        sesion.save()
        respuesta = client.get("/")
        assert respuesta.status_code == 302 and "/seguridad/entrar/" in respuesta["Location"]

    def test_cerrar_otra_sesion_propia_y_no_ajena(self, client):
        u = usuario(rol="tecnico")
        otro_cliente = client.__class__()
        entrar(otro_cliente, "ana")
        entrar(client, "ana")
        otra = SesionUsuario.objects.exclude(clave_sesion=client.session.session_key).get(usuario=u)
        ajeno = usuario("beto", rol="tecnico")
        cliente_ajeno = client.__class__()
        entrar(cliente_ajeno, "beto")
        sesion_ajena = SesionUsuario.objects.get(usuario=ajeno)
        client.post("/seguridad/sesiones/", {"sesion": sesion_ajena.pk})
        assert SesionUsuario.objects.filter(pk=sesion_ajena.pk).exists()
        client.post("/seguridad/sesiones/", {"sesion": otra.pk})
        assert not SesionUsuario.objects.filter(pk=otra.pk).exists()
        assert otro_cliente.get("/").status_code == 302  # la otra sesión quedó cerrada

    def test_cierre_de_sesion_por_post(self, client):
        usuario(rol="tecnico")
        entrar(client, "ana")
        client.post("/seguridad/salir/")
        assert client.get("/").status_code == 302
        assert Bitacora.objects.filter(accion="cierre_sesion").exists()


class TestCabeceras:
    def test_csp_y_otras(self, client):
        respuesta = client.get("/seguridad/entrar/")
        csp = respuesta["Content-Security-Policy"]
        assert (
            "script-src 'self'" in csp
            and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
        )
        assert "frame-ancestors 'none'" in csp
        assert "Permissions-Policy" in respuesta


class TestAdminYEscalada:
    def test_administrador_no_puede_volverse_superusuario(self, client):
        admin = usuario("adm", rol="administrador")
        assert User.objects.get(pk=admin.pk).is_staff  # acceso al admin por su rol
        verificar_cliente(client, admin)
        objetivo = usuario("beto", rol="tecnico")
        client.post(
            f"/admin/auth/user/{objetivo.pk}/change/",
            {
                "username": "beto",
                "is_active": "on",
                "is_superuser": "on",
                "is_staff": "on",
                "date_joined_0": "2026-01-01",
                "date_joined_1": "00:00:00",
            },
        )
        objetivo.refresh_from_db()
        assert not objetivo.is_superuser and not objetivo.is_staff

    def test_tecnico_no_entra_al_admin(self, client):
        tecnico = usuario(rol="tecnico")
        tecnico.is_staff = True  # aunque alguien marque staff, puede() no le da módulos
        tecnico.save()
        verificar_cliente(client, tecnico)
        respuesta = client.get("/admin/core/unidad/")
        assert respuesta.status_code in (302, 403)

    def test_auditor_ve_bitacora_pero_no_modifica_catalogos(self, client):
        auditor = usuario("aud", rol="auditor")
        verificar_cliente(client, auditor)
        assert client.get("/admin/auditoria/bitacora/").status_code == 200
        assert client.get("/admin/core/unidad/add/").status_code == 403

    def test_cambio_de_roles_queda_en_bitacora(self, client):
        admin = usuario("adm", rol="administrador")
        verificar_cliente(client, admin)
        objetivo = usuario("beto", rol="tecnico")
        director = Group.objects.get(name="director")
        respuesta = client.post(
            f"/admin/auth/user/{objetivo.pk}/change/",
            {"username": "beto", "is_active": "on", "groups": [director.pk]},
        )
        assert respuesta.status_code == 302, respuesta.content[:500]
        assert Bitacora.objects.filter(
            accion="roles_modificados", objeto_id=str(objetivo.pk)
        ).exists()


class TestCuentasYRespaldo:
    def test_desactiva_cuentas_sin_cargo(self):
        unidad = Unidad.objects.create(sigla="UZ", nombre="U")
        cargo = Cargo.objects.create(unidad=unidad, codigo="UZ-1", nombre="C")
        u = usuario(rol="tecnico")
        persona = Persona.objects.create(nombres="Ana", apellidos="Z", usuario=u)
        ocupacion = core_services.asignar_cargo(
            persona=persona, cargo=cargo, tipo="titular", desde=dt.date(2026, 1, 1)
        )
        assert services.desactivar_cuentas_sin_cargo(dt.date(2026, 6, 1)) == []
        core_services.terminar_ocupacion(ocupacion=ocupacion, hasta=dt.date(2026, 5, 31))
        assert services.desactivar_cuentas_sin_cargo(dt.date(2026, 6, 1)) == ["ana"]
        u.refresh_from_db()
        assert not u.is_active

    def test_no_desactiva_cuentas_sin_persona(self):
        usuario("soporte", rol="administrador")
        assert services.desactivar_cuentas_sin_cargo() == []

    @override_settings(RESPALDO_VIGILAR=True, ALERTAS_EMAIL=["admin@ejemplo.invalid"])
    def test_alerta_sin_respaldo_una_vez(self):
        assert tareas.vigilar_respaldo() == "alerta enviada"
        assert tareas.vigilar_respaldo() == "sin respaldo reciente (ya alertado)"
        assert len(mail.outbox) == 1

    @override_settings(RESPALDO_VIGILAR=True)
    def test_respaldo_reciente_no_alerta(self):
        bitacora.registrar_seguridad(accion="respaldo_ok")
        assert tareas.vigilar_respaldo().startswith("último respaldo")


class TestIpCliente:
    def _req(self, xff=None, remote="10.0.0.2"):
        meta = {"REMOTE_ADDR": remote}
        if xff:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().get("/", **meta)

    @override_settings(PROXIES_CONFIABLES=0)
    def test_sin_proxy_ignora_xff(self):
        assert ip_cliente(self._req("1.2.3.4")) == "10.0.0.2"

    @override_settings(PROXIES_CONFIABLES=1)
    def test_un_proxy_toma_la_ultima_y_no_la_falsificada(self):
        assert ip_cliente(self._req("6.6.6.6, 200.87.1.10")) == "200.87.1.10"

    @override_settings(PROXIES_CONFIABLES=1)
    def test_valor_invalido(self):
        assert ip_cliente(self._req("no-es-ip")) is None
