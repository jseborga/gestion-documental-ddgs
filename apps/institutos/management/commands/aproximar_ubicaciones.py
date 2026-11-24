"""Ubica de forma APROXIMADA (por municipio) los institutos sin ubicación."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.institutos import geocodificacion, services
from apps.institutos.models import Instituto, Precision


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
        pendientes = (
            Instituto.objects.filter(lat__isnull=True)
            .exclude(municipio="")
            .order_by("numero")[:maximo]
        )
        cache: dict[tuple[str, str], object] = {}
        ubicados = sin_resultado = fuera = 0
        for inst in pendientes:
            clave = (inst.municipio.strip().lower(), inst.provincia.strip().lower())
            if clave not in cache:
                try:
                    cache[clave] = geocodificacion.buscar_municipio(inst.municipio, inst.provincia)
                except geocodificacion.ErrorGeocodificacion as error:
                    raise CommandError(str(error)) from error
                except OSError as error:
                    raise CommandError(f"No se pudo consultar Nominatim: {error}") from error
                geocodificacion.pausa()
            coordenadas = cache[clave]
            if coordenadas is None:
                sin_resultado += 1
                self.stdout.write(f"  Sin resultado: {inst.numero} {inst.municipio}")
                continue
            lat, lon = coordenadas
            try:
                services.validar_en_zona(lat, lon)
            except ValidationError:
                fuera += 1
                self.stdout.write(f"  Fuera de zona (descartado): {inst.numero} {inst.municipio}")
                continue
            if not simular:
                services.registrar_ubicacion(
                    instituto=inst,
                    lat=lat,
                    lon=lon,
                    precision=Precision.APROXIMADA,
                    fuente=f"Aproximada por municipio ({inst.municipio}) — OpenStreetMap Nominatim",
                )
            ubicados += 1
        modo = "SIMULACIÓN: " if simular else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{modo}{ubicados} ubicados de forma aproximada, {sin_resultado} sin resultado, "
                f"{fuera} fuera de zona. Corrija cada uno desde su ficha."
            )
        )
