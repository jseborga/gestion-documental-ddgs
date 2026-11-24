"""Pruebas: PostgreSQL real (políticas §5), archivos en disco temporal."""

import os
import tempfile

os.environ.setdefault("DJANGO_SECRET_KEY", "clave-solo-para-pruebas")
os.environ.setdefault(
    "DATABASE_URL", "postgres://gestion:gestion@localhost:5432/gestion_documental"
)
os.environ["S3_ENDPOINT_URL"] = ""

from .base import *  # noqa: E402, F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": tempfile.mkdtemp(prefix="gd-media-")},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
