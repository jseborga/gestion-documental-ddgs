"""Controles transversales: duración máxima de sesión, segundo factor y cabeceras."""

import time

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from . import roles, services

# Rutas accesibles sin segundo factor verificado (las necesarias para verificarlo).
RUTAS_LIBRES = (
    "/seguridad/entrar/",
    "/seguridad/salir/",
    "/seguridad/2fa/verificar/",
    "/seguridad/2fa/configurar/",
    "/static/",
    "/api/v1/salud/",
)


def _ruta_libre(path: str) -> bool:
    return path.startswith(RUTAS_LIBRES)


class SesionMaximaMiddleware:
    """Cierra la sesión al superar `SESION_MAXIMA_HORAS` desde el inicio, aun con actividad."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            inicio = request.session.get("inicio_sesion")
            maximo = settings.SESION_MAXIMA_HORAS * 3600
            if inicio is None or time.time() - float(inicio) > maximo:
                logout(request)
                if request.path.startswith("/api/"):
                    return JsonResponse({"detalle": "Sesión expirada."}, status=401)
                return redirect(f"{reverse('seguridad:entrar')}?next={request.path}")
        return self.get_response(request)


class SegundoFactorMiddleware:
    """Exige verificar el segundo factor a quien lo tenga obligatorio o configurado.

    Va después de `django_otp.middleware.OTPMiddleware`, que agrega `user.is_verified()`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        if usuario.is_authenticated and not _ruta_libre(request.path) and not usuario.is_verified():
            tiene_dispositivo = services.dispositivo_totp_confirmado(usuario) is not None
            if tiene_dispositivo or roles.requiere_segundo_factor(usuario):
                if request.path.startswith("/api/"):
                    return JsonResponse({"detalle": "Se requiere segundo factor."}, status=403)
                destino = "seguridad:verificar" if tiene_dispositivo else "seguridad:configurar_2fa"
                return redirect(f"{reverse(destino)}?next={request.path}")
        return self.get_response(request)


class CabecerasSeguridadMiddleware:
    """CSP y otras cabeceras (docs/seguridad.md §2.7)."""

    def __init__(self, get_response):
        self.get_response = get_response
        img = " ".join(["'self'", "data:", *settings.CSP_IMG_SRC_EXTRA])
        self.csp = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self'",
                # El admin de Django usa atributos style; los scripts siguen sin 'unsafe-inline'.
                "style-src 'self' 'unsafe-inline'",
                f"img-src {img}",
                "font-src 'self'",
                "connect-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta.setdefault("Content-Security-Policy", self.csp)
        respuesta.setdefault(
            "Permissions-Policy", "geolocation=(self), camera=(self), microphone=(), payment=()"
        )
        respuesta.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.user.is_authenticated if hasattr(request, "user") else False:
            respuesta.setdefault("Cache-Control", "no-store")
        return respuesta
