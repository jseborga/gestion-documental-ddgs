"""Configuración común. Todo valor institucional o secreto viene de variables de entorno."""

import datetime as dt
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    S3_ENDPOINT_URL=(str, ""),
    CITE_RESERVA_HORAS=(int, 0),
    ADJUNTO_MAX_MB=(int, 25),
    INTEROP_HABILITADO=(bool, False),
    SESION_INACTIVIDAD_MIN=(int, 30),
    INSTITUCION_NOMBRE=(str, "Institución"),
    INSTITUCION_SIGLA=(str, "INST"),
    PROXIES_CONFIABLES=(int, 0),
    SESION_MAXIMA_HORAS=(int, 10),
    MFA_OBLIGATORIO_ROLES=(list, ["administrador", "director", "auditor"]),
    MFA_OBLIGATORIO_TODOS=(bool, False),
    AXES_FAILURE_LIMIT=(int, 5),
    AXES_BLOQUEO_MINUTOS=(int, 15),
    ALERTAS_EMAIL=(list, []),
    RESPALDO_VIGILAR=(bool, False),
    RESPALDO_ALERTA_HORAS=(int, 26),
    CSP_IMG_SRC_EXTRA=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "storages",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "axes",
    "apps.core",
    "apps.auditoria",
    "apps.eventos",
    "apps.seguridad",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.seguridad.middleware.CabecerasSeguridadMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.seguridad.middleware.SesionMaximaMiddleware",
    "apps.seguridad.middleware.SegundoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "seguridad:entrar"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "seguridad:entrar"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Archivos: API S3 (SeaweedFS por defecto, ADR-04). Sin S3 configurado se usa disco local.
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL")
if S3_ENDPOINT_URL:
    _almacen_por_defecto = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": S3_ENDPOINT_URL,
            "access_key": env("S3_ACCESS_KEY"),
            "secret_key": env("S3_SECRET_KEY"),
            "bucket_name": env("S3_BUCKET"),
            "region_name": env("S3_REGION", default="us-east-1"),
            "default_acl": None,  # los archivos nunca son públicos
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
            "addressing_style": "path",
        },
    }
else:
    _almacen_por_defecto = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / "media"},
    }

STORAGES = {
    "default": _almacen_por_defecto,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="correspondencia@localhost")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "30/minute", "user": "300/minute"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API de gestión documental",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SESSION_COOKIE_AGE = env("SESION_INACTIVIDAD_MIN") * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Seguridad (docs/seguridad.md)
# Número de proxies inversos confiables delante de la app (EasyPanel/Traefik = 1).
PROXIES_CONFIABLES = env("PROXIES_CONFIABLES")
SESION_MAXIMA_HORAS = env("SESION_MAXIMA_HORAS")
MFA_OBLIGATORIO_ROLES = env("MFA_OBLIGATORIO_ROLES")
MFA_OBLIGATORIO_TODOS = env("MFA_OBLIGATORIO_TODOS")
ALERTAS_EMAIL = env("ALERTAS_EMAIL")
CSP_IMG_SRC_EXTRA = env("CSP_IMG_SRC_EXTRA")
RESPALDO_VIGILAR = env("RESPALDO_VIGILAR")
RESPALDO_ALERTA_HORAS = env("RESPALDO_ALERTA_HORAS")

AXES_FAILURE_LIMIT = env("AXES_FAILURE_LIMIT")
AXES_COOLOFF_TIME = dt.timedelta(minutes=env("AXES_BLOQUEO_MINUTOS"))
# Bloqueo por combinación usuario + IP: evita que un tercero bloquee a otro usuario a propósito.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "seguridad/bloqueado.html"
AXES_CLIENT_IP_CALLABLE = "apps.seguridad.red.ip_cliente"
AXES_VERBOSE = False

# Datos de la institución (SPEC §16: nada institucional fijo en el código)
INSTITUCION_NOMBRE = env("INSTITUCION_NOMBRE")
INSTITUCION_SIGLA = env("INSTITUCION_SIGLA")
OTP_TOTP_ISSUER = INSTITUCION_SIGLA

# Reglas de negocio
CITE_RESERVA_HORAS = env("CITE_RESERVA_HORAS")
if not 0 <= CITE_RESERVA_HORAS <= 24:
    raise ValueError("CITE_RESERVA_HORAS debe estar entre 0 y 24 (levantamiento A5).")
ADJUNTO_MAX_MB = env("ADJUNTO_MAX_MB")
INTEROP_HABILITADO = env("INTEROP_HABILITADO")

VERSION = "0.1.0"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"consola": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["consola"], "level": "INFO"},
}
