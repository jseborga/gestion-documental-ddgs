"""Registro en bitácora de seguridad de inicios, cierres, fallos y bloqueos de sesión."""

from axes.signals import user_locked_out
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from apps.auditoria import selectors as bitacora_lectura
from apps.auditoria import services as bitacora

from . import services
from .red import ip_cliente

UMBRAL_FALLOS = 10
VENTANA_MINUTOS = 10


def _ip(request):
    return ip_cliente(request) if request is not None else None


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    ip = _ip(request)
    request.session["inicio_sesion"] = timezone.now().timestamp()
    services.registrar_sesion(
        usuario=user,
        clave_sesion=request.session.session_key or "",
        ip=ip,
        agente=request.META.get("HTTP_USER_AGENT", ""),
    )
    bitacora.registrar_seguridad(accion="inicio_sesion", actor=user, objeto=user, ip=ip)
    if user.is_superuser:
        bitacora.registrar_seguridad(accion="uso_superusuario", actor=user, objeto=user, ip=ip)
        services.alertar(
            "Inicio de sesión de superusuario",
            f"El superusuario '{user.get_username()}' inició sesión desde {ip or 'IP desconocida'} "
            f"el {timezone.localtime():%d/%m/%Y %H:%M}. Debe usarse solo en emergencias.",
        )


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if request is not None:
        services.olvidar_sesion(request.session.session_key)
    if user is not None:
        bitacora.registrar_seguridad(
            accion="cierre_sesion", actor=user, objeto=user, ip=_ip(request)
        )


@receiver(user_login_failed)
def al_fallar_inicio(sender, credentials, request=None, **kwargs):
    # Solo se guarda el id de un usuario existente: lo tecleado puede ser una contraseña
    # escrita por error en el campo de usuario, o un texto largo para provocar errores.
    tecleado = str(credentials.get("username", ""))[:150]
    existente = (
        get_user_model().objects.filter(username=tecleado).values_list("pk", flat=True).first()
    )
    bitacora.registrar_seguridad(
        accion="inicio_sesion_fallido",
        objeto_tipo="usuario",
        objeto_id=existente if existente is not None else "desconocido",
        ip=_ip(request),
    )
    fallos = bitacora_lectura.contar_recientes("inicio_sesion_fallido", VENTANA_MINUTOS)
    alerta_reciente = bitacora_lectura.contar_recientes("alerta_fallos_sesion", VENTANA_MINUTOS)
    if fallos >= UMBRAL_FALLOS and not alerta_reciente:
        bitacora.registrar_seguridad(accion="alerta_fallos_sesion", despues={"fallos": fallos})
        services.alertar(
            "Muchos intentos fallidos de inicio de sesión",
            f"Hubo {fallos} intentos fallidos en los últimos {VENTANA_MINUTOS} minutos.",
        )


@receiver(user_locked_out)
def al_bloquear(sender, request, username, ip_address, **kwargs):
    existente = (
        get_user_model()
        .objects.filter(username=str(username or "")[:150])
        .values_list("pk", flat=True)
        .first()
    )
    bitacora.registrar_seguridad(
        accion="cuenta_bloqueada_por_intentos",
        objeto_tipo="usuario",
        objeto_id=existente if existente is not None else "desconocido",
        ip=ip_address,
    )


@receiver(m2m_changed, sender=get_user_model().groups.through)
def sincronizar_acceso_admin(sender, instance, action, **kwargs):
    """Acceso al panel de administración solo para administrador y auditor."""
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not isinstance(instance, get_user_model()) or instance.is_superuser:
        return
    from .roles import Rol

    debe = instance.groups.filter(name__in=[Rol.ADMINISTRADOR, Rol.AUDITOR]).exists()
    if instance.is_staff != debe:
        instance.is_staff = debe
        instance.save(update_fields=["is_staff"])
