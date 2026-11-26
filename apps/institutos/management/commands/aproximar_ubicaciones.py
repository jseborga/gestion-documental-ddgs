"""Ubica de forma APROXIMADA (por municipio) los institutos sin ubicación."""

from django.core.management.base import BaseCommand, CommandError

from apps.institutos import geocodificacion, services


class Command(BaseCommand):
    help = (
        "Ubicación aproximada por municipio con OpenStreetMap Nominatim (marcada como aproximada)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="Consultar sin guardar")
        parser.add_argument(
            "--maximo", type=int, default=100, help="Máximo de institutos a procesar"
        )

    def handle(self, *args, simular=False, maximo=100, **opciones):
        try:
            informe = services.aproximar_ubicaciones(maximo=maximo, simular=simular)
        except geocodificacion.ErrorGeocodificacion as error:
            raise CommandError(str(error)) from error
        except OSError as error:
            raise CommandError(f"No se pudo consultar Nominatim: {error}") from error
        for etiqueta in informe.sin_resultado:
            self.stdout.write(f"  Sin resultado: {etiqueta}")
        for etiqueta in informe.fuera_de_zona:
            self.stdout.write(f"  Fuera de zona (descartado): {etiqueta}")
        self.stdout.write(self.style.SUCCESS(informe.resumen()))
