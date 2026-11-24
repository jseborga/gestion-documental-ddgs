"""Worker: procesa el outbox y las tareas periódicas (una vez o en bucle con --loop)."""

import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.eventos import services


class Command(BaseCommand):
    help = "Procesa eventos pendientes del outbox y tareas periódicas."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Procesar en bucle.")
        parser.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre ciclos.")

    def ciclo(self) -> tuple[int, list[str]]:
        return services.procesar_lote(), services.ejecutar_tareas_vencidas()

    def handle(self, *args, **opciones):
        if not opciones["loop"]:
            n, tareas = self.ciclo()
            self.stdout.write(
                f"Eventos procesados: {n}. Tareas ejecutadas: {', '.join(tareas) or '-'}"
            )
            return
        detener = {"valor": False}

        def parar(*_):
            detener["valor"] = True

        signal.signal(signal.SIGTERM, parar)
        signal.signal(signal.SIGINT, parar)
        self.stdout.write("Procesador de eventos iniciado.")
        while not detener["valor"]:
            close_old_connections()
            try:
                self.ciclo()
            except Exception:  # p. ej. la base reinicia: se reintenta en el siguiente ciclo
                self.stderr.write("Error en el ciclo del worker; se reintenta.")
            time.sleep(opciones["intervalo"])
        self.stdout.write("Procesador de eventos detenido.")
