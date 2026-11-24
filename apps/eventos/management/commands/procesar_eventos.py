"""Procesa la tabla outbox. En el paso 1 solo mantiene vivo el proceso `worker`;
los consumidores se agregan en el paso 3 (CLAUDE.md)."""

import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Procesa eventos pendientes del outbox (una vez o en bucle con --loop)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Procesar en bucle.")
        parser.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre ciclos.")

    def procesar_una_vez(self) -> int:
        """Devuelve la cantidad de eventos procesados. Sin consumidores todavía."""
        return 0

    def handle(self, *args, **opciones):
        if not opciones["loop"]:
            n = self.procesar_una_vez()
            self.stdout.write(f"Eventos procesados: {n}")
            return
        self.stdout.write("Procesador de eventos iniciado.")
        while True:
            self.procesar_una_vez()
            time.sleep(opciones["intervalo"])
