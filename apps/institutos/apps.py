from django.apps import AppConfig


class InstitutosConfig(AppConfig):
    name = "apps.institutos"
    verbose_name = "Institutos"

    def ready(self):
        from . import tareas  # noqa: F401  (registra el consumidor de eventos)
