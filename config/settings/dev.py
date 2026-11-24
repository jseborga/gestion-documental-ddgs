"""Desarrollo local con Docker Compose. Datos sintéticos únicamente."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env("DJANGO_DEBUG", default=True)

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
