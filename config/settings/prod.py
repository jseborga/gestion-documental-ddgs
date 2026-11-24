"""Producción del piloto: detrás de un proxy inverso con TLS."""

from .base import *  # noqa: F403
from .base import env

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
# La salud se consulta por HTTP dentro de la red de Docker (healthcheck del contenedor).
SECURE_REDIRECT_EXEMPT = [r"^api/v1/salud/$"]

# La precarga HSTS es un compromiso irreversible del dominio: se decide aparte (docs/seguridad.md).
SILENCED_SYSTEM_CHECKS = ["security.W021"]
