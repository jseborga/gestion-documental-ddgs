"""Pantallas de inicio de sesión, segundo factor y sesiones."""

import base64
from io import StringIO

import django_otp
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.auditoria import services as bitacora
from apps.core import selectors as core_selectors

from . import roles, services
from .forms import CodigoForm
from .red import ip_cliente


def _siguiente(request, por_defecto="/"):
    destino = request.POST.get("next") or request.GET.get("next") or por_defecto
    if url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return por_defecto


class EntrarView(auth_views.LoginView):
    template_name = "seguridad/entrar.html"
    redirect_authenticated_user = True


@login_required
def verificar(request):
    """Pide el código TOTP o un código de recuperación después de la contraseña."""
    if request.user.is_verified():
        return redirect(_siguiente(request))
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        codigo = form.cleaned_data["codigo"].strip().lower()
        dispositivo = django_otp.match_token(request.user, codigo)
        if dispositivo is not None:
            django_otp.login(request, dispositivo)
            request.session.cycle_key()  # rotación al elevar privilegios
            services.registrar_sesion(
                usuario=request.user,
                clave_sesion=request.session.session_key or "",
                ip=ip_cliente(request),
                agente=request.META.get("HTTP_USER_AGENT", ""),
            )
            es_recuperacion = dispositivo.persistent_id.startswith("otp_static")
            bitacora.registrar_seguridad(
                accion="segundo_factor_recuperacion" if es_recuperacion else "segundo_factor_ok",
                actor=request.user,
                objeto=request.user,
                ip=ip_cliente(request),
            )
            if es_recuperacion:
                restantes = dispositivo.token_set.count()
                messages.warning(
                    request,
                    f"Usó un código de recuperación. Le quedan {restantes}. "
                    "Genere nuevos desde «Mis sesiones».",
                )
            return redirect(_siguiente(request))
        bitacora.registrar_seguridad(
            accion="segundo_factor_fallido",
            actor=request.user,
            objeto=request.user,
            ip=ip_cliente(request),
        )
        form.add_error(
            "codigo",
            "Código incorrecto o vencido. Tras varios errores el sistema exige esperar "
            "unos segundos más cada vez.",
        )
    return render(request, "seguridad/verificar.html", {"form": form, "next": _siguiente(request)})


def _qr_svg(texto: str) -> str:
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    salida = StringIO()
    salida.write(imagen.to_string(encoding="unicode"))
    return salida.getvalue()


@login_required
def configurar_2fa(request):
    """Alta del segundo factor: QR, confirmación con un código y códigos de recuperación."""
    ya_tiene = services.dispositivo_totp_confirmado(request.user) is not None
    if ya_tiene and not request.user.is_verified():
        return redirect("seguridad:verificar")
    dispositivo = services.iniciar_configuracion_totp(request.user)
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        codigos = services.confirmar_totp(
            usuario=request.user,
            dispositivo=dispositivo,
            codigo=form.cleaned_data["codigo"],
            ip=ip_cliente(request),
        )
        if codigos is not None:
            django_otp.login(request, dispositivo)
            request.session.cycle_key()
            return render(
                request,
                "seguridad/codigos_recuperacion.html",
                {"codigos": codigos, "next": _siguiente(request)},
            )
        form.add_error(
            "codigo", "El código no coincide. Revise la hora del celular e intente de nuevo."
        )
    secreto = base64.b32encode(dispositivo.bin_key).decode()
    return render(
        request,
        "seguridad/configurar_2fa.html",
        {
            "form": form,
            "qr": _qr_svg(dispositivo.config_url),
            "secreto": " ".join(secreto[i : i + 4] for i in range(0, len(secreto), 4)),
            "reemplaza": ya_tiene,
            "next": _siguiente(request),
        },
    )


@login_required
@require_POST
def regenerar_codigos(request):
    if not request.user.is_verified():
        return redirect("seguridad:verificar")
    codigos = services.generar_codigos_recuperacion(request.user)
    bitacora.registrar_seguridad(
        accion="codigos_recuperacion_regenerados",
        actor=request.user,
        objeto=request.user,
        ip=ip_cliente(request),
    )
    return render(request, "seguridad/codigos_recuperacion.html", {"codigos": codigos, "next": "/"})


@login_required
def mis_sesiones(request):
    if request.method == "POST":
        try:
            sesion_id = int(request.POST.get("sesion", ""))
        except ValueError:
            sesion_id = 0
        if services.cerrar_sesion_remota(
            usuario=request.user, sesion_id=sesion_id, ip=ip_cliente(request)
        ):
            messages.success(request, "Sesión cerrada.")
        return redirect("seguridad:mis_sesiones")
    sesiones = services.sesiones_activas(request.user)
    return render(
        request,
        "seguridad/mis_sesiones.html",
        {"sesiones": sesiones, "actual": request.session.session_key},
    )


@login_required
def inicio(request):
    persona = getattr(request.user, "persona", None)
    cargos = list(core_selectors.cargos_vigentes(persona)) if persona else []
    return render(
        request,
        "inicio.html",
        {
            "persona": persona,
            "cargos": cargos,
            "roles": sorted(roles.roles_de(request.user)),
            "tiene_2fa": services.dispositivo_totp_confirmado(request.user) is not None,
            "institucion": settings.INSTITUCION_NOMBRE,
        },
    )
