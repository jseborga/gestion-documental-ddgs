"""Importa las planillas de institutos. Primero ejecutar con --simular y revisar el informe."""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Unidad
from apps.institutos import importador, services


class Command(BaseCommand):
    help = "Importa la planilla de datos y la ficha técnica de institutos (formato v1)."

    def add_arguments(self, parser):
        parser.add_argument("--datos", type=Path, required=True, help="Planilla de datos (.xlsx)")
        parser.add_argument("--ficha", type=Path, required=True, help="Ficha técnica (.xlsx)")
        parser.add_argument("--unidad", required=True, help="Sigla de la unidad responsable")
        parser.add_argument("--simular", action="store_true", help="Leer y validar sin guardar")
        parser.add_argument(
            "--observaciones-extra",
            type=Path,
            help="CSV opcional 'numero;texto' con observaciones manuales (no se versiona)",
        )
        parser.add_argument("--informe", type=Path, help="CSV de salida con las observaciones")

    def handle(self, *args, **o):
        unidad = Unidad.objects.filter(sigla=o["unidad"]).first()
        if unidad is None:
            raise CommandError(f"No existe la unidad '{o['unidad']}'.")
        extra = self._leer_extra(o["observaciones_extra"]) if o["observaciones_extra"] else []
        try:
            lectura = importador.leer(o["datos"], o["ficha"], extra)
        except importador.ArchivoNoValido as error:
            raise CommandError(str(error)) from error
        informe = services.importar(lectura=lectura, unidad=unidad, simular=o["simular"])
        self.stdout.write(self.style.SUCCESS(informe.resumen()))
        for numero, texto in sorted(informe.observaciones, key=lambda x: (x[0] is None, x[0] or 0)):
            self.stdout.write(f"  [{numero if numero is not None else '-'}] {texto}")
        if o["informe"]:
            with o["informe"].open("w", newline="", encoding="utf-8") as salida:
                escritor = csv.writer(salida, delimiter=";")
                escritor.writerow(["numero", "observacion"])
                escritor.writerows(informe.observaciones)

    def _leer_extra(self, ruta: Path) -> list[tuple[int | None, str]]:
        if ruta.suffix.lower() != ".csv" or ruta.stat().st_size > 1024 * 1024:
            raise CommandError("Las observaciones extra deben ser un CSV de hasta 1 MB.")
        filas = []
        with ruta.open(encoding="utf-8") as archivo:
            for fila in csv.reader(archivo, delimiter=";"):
                if len(fila) >= 2 and fila[0].strip().isdigit():
                    filas.append((int(fila[0]), fila[1].strip()[:500]))
        return filas
