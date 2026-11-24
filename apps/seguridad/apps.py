from django.apps import AppConfig


class SeguridadConfig(AppConfig):
    name = "apps.seguridad"
    verbose_name = "Seguridad"

    def ready(self):
        from . import senales, tareas  # noqa: F401  (registra señales y tareas periódicas)
