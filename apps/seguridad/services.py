"""Operaciones de seguridad: alertas, sesiones, segundo factor y cuentas."""

import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.auditoria import services as bitacora
from apps.core import selectors as core_selectors
from apps.eventos import services as eventos

from .models import SesionUsuario

logger = logging.getLogger(__name__)

CANTIDAD_CODIGOS_RECUPERACION = 10


def alertar(asunto: str, mensaje: str) -> None:
    """Correo al administrador. Nunca interrumpe la operación si el correo falla."""
    destinatarios = settings.ALERTAS_EMAIL
    logger.warning("ALERTA DE SEGURIDAD: %s", asunto)
    if not destinatarios:
        return
    try:
        send_mail(
            f"[{settings.INSTITUCION_SIGLA}] {asunto}",
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            destinatarios,
            fail_silently=False,
        )
    except Exception:
        logger.exception("No se pudo enviar la alerta por correo")


# --- Sesiones -------------------------------------------------------------------------


def registrar_sesion(*, usuario, clave_sesion: str, ip: str | None, agente: str) -> None:
    SesionUsuario.objects.update_or_create(
        clave_sesion=clave_sesion,
        defaults={"usuario": usuario, "ip": ip, "agente": agente[:255]},
    )


def olvidar_sesion(clave_sesion: str | None) -> None:
    if clave_sesion:
        SesionUsuario.objects.filter(clave_sesion=clave_sesion).delete()


@transaction.atomic
def cerrar_sesion_remota(*, usuario, sesion_id: int, ip: str | None = None) -> bool:
    """Cierra otra sesión del mismo usuario. Devuelve False si no es suya."""
    sesion = SesionUsuario.objects.filter(pk=sesion_id, usuario=usuario).first()
    if sesion is None:
        return False
    SessionStore(session_key=sesion.clave_sesion).delete()
    sesion.delete()
    bitacora.registrar_seguridad(
        accion="sesion_cerrada_remota",
        actor=usuario,
        objeto_tipo="sesion",
        objeto_id=sesion_id,
        ip=ip,
    )
    return True


def sesiones_activas(usuario):
    """Sesiones del usuario que siguen vivas; limpia las que ya expiraron."""
    vivas = []
    for sesion in SesionUsuario.objects.filter(usuario=usuario):
        if SessionStore(session_key=sesion.clave_sesion).exists(sesion.clave_sesion):
            vivas.append(sesion)
        else:
            sesion.delete()
    return vivas


# --- Segundo factor -------------------------------------------------------------------


def dispositivo_totp_confirmado(usuario) -> TOTPDevice | None:
    return TOTPDevice.objects.filter(user=usuario, confirmed=True).first()


def iniciar_configuracion_totp(usuario) -> TOTPDevice:
    """Crea (o reutiliza) un dispositivo TOTP sin confirmar para mostrar el QR."""
    dispositivo = TOTPDevice.objects.filter(user=usuario, confirmed=False).first()
    if dispositivo is None:
        dispositivo = TOTPDevice.objects.create(
            user=usuario, name="Aplicación de autenticación", confirmed=False
        )
    return dispositivo


@transaction.atomic
def confirmar_totp(
    *, usuario, dispositivo: TOTPDevice, codigo: str, ip: str | None
) -> list[str] | None:
    """Confirma el dispositivo si el código es válido. Devuelve los códigos de recuperación."""
    if dispositivo.user_id != usuario.pk or not dispositivo.verify_token(codigo.strip()):
        return None
    TOTPDevice.objects.filter(user=usuario, confirmed=True).exclude(pk=dispositivo.pk).delete()
    dispositivo.confirmed = True
    dispositivo.save(update_fields=["confirmed"])
    codigos = generar_codigos_recuperacion(usuario)
    bitacora.registrar_seguridad(
        accion="segundo_factor_activado", actor=usuario, objeto=usuario, ip=ip
    )
    eventos.publicar(
        tipo="seguridad.segundo_factor_activado", agregado="usuario", agregado_id=usuario.pk
    )
    return codigos


def generar_codigos_recuperacion(usuario) -> list[str]:
    """Reemplaza los códigos de recuperación; se muestran una sola vez."""
    dispositivo, _ = StaticDevice.objects.get_or_create(
        user=usuario, name="Códigos de recuperación"
    )
    dispositivo.token_set.all().delete()
    codigos = [
        f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
        for _ in range(CANTIDAD_CODIGOS_RECUPERACION)
    ]
    StaticToken.objects.bulk_create(StaticToken(device=dispositivo, token=c) for c in codigos)
    return codigos


# --- Cuentas --------------------------------------------------------------------------


def desactivar_cuentas_sin_cargo(fecha=None) -> list[str]:
    """Desactiva usuarios cuya persona ya no ocupa ningún cargo (§2.1)."""
    fecha = fecha or timezone.localdate()
    Usuario = get_user_model()
    candidatos = Usuario.objects.filter(
        is_active=True,
        is_superuser=False,
        persona__isnull=False,
        persona__ocupaciones__isnull=False,
    ).distinct()
    desactivados = []
    for usuario in candidatos.select_related("persona"):
        if core_selectors.cargos_vigentes(usuario.persona, fecha).exists():
            continue
        with transaction.atomic():
            usuario.is_active = False
            usuario.save(update_fields=["is_active"])
            for sesion in SesionUsuario.objects.filter(usuario=usuario):
                SessionStore(session_key=sesion.clave_sesion).delete()
                sesion.delete()
            bitacora.registrar_seguridad(
                accion="cuenta_desactivada_sin_cargo",
                objeto=usuario,
                despues={"is_active": False, "fecha": fecha},
            )
            eventos.publicar(
                tipo="seguridad.cuenta_desactivada", agregado="usuario", agregado_id=usuario.pk
            )
        desactivados.append(usuario.get_username())
    if desactivados:
        alertar(
            "Cuentas desactivadas por fin de cargo",
            "Se desactivaron estas cuentas porque ya no ocupan ningún cargo:\n- "
            + "\n- ".join(desactivados),
        )
    return desactivados
