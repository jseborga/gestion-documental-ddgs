"""Carga datos sintéticos de ejemplo. Idempotente: se puede ejecutar varias veces."""

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import services
from apps.core.models import (
    Cargo,
    InstitucionExterna,
    OcupacionCargo,
    Persona,
    Proceso,
    Proyecto,
    Unidad,
)

ARCHIVO_POR_DEFECTO = Path(settings.BASE_DIR) / "seeds" / "estructura_ejemplo.json"


def _fecha(valor: str | None) -> dt.date | None:
    return dt.date.fromisoformat(valor) if valor else None


class Command(BaseCommand):
    help = "Carga la estructura y los datos sintéticos de seeds/ (no usar con datos reales)."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", type=Path, default=ARCHIVO_POR_DEFECTO)

    @transaction.atomic
    def handle(self, *args, **opciones):
        ruta: Path = opciones["archivo"]
        if not ruta.exists():
            raise CommandError(f"No existe el archivo de semillas: {ruta}")
        datos = json.loads(ruta.read_text(encoding="utf-8"))

        unidades: dict[str, Unidad] = {}
        for u in datos["unidades"]:  # el archivo lista padres antes que hijas
            unidades[u["sigla"]], _ = Unidad.objects.update_or_create(
                sigla=u["sigla"],
                defaults={
                    "nombre": u["nombre"],
                    "nivel": u["nivel"],
                    "padre": unidades.get(u["padre"]) if u["padre"] else None,
                    "prefijo_cite": u["prefijo_cite"],
                },
            )

        cargos: dict[str, Cargo] = {}
        for c in datos["cargos"]:
            cargos[c["codigo"]], _ = Cargo.objects.update_or_create(
                codigo=c["codigo"],
                defaults={
                    "unidad": unidades[c["unidad"]],
                    "nombre": c["nombre"],
                    "puede_firmar": c["puede_firmar"],
                    "es_ventanilla": c["es_ventanilla"],
                },
            )

        personas: dict[str, Persona] = {}
        for p in datos["personas"]:
            personas[p["clave"]], _ = Persona.objects.update_or_create(
                email=p["email"],
                defaults={
                    "nombres": p["nombres"],
                    "apellidos": p["apellidos"],
                    "nombre_corto": p["nombre_corto"],
                },
            )

        nuevas = 0
        for o in datos["ocupaciones"]:
            existe = OcupacionCargo.objects.filter(
                persona=personas[o["persona"]],
                cargo=cargos[o["cargo"]],
                tipo=o["tipo"],
                desde=_fecha(o["desde"]),
            ).exists()
            if not existe:
                services.asignar_cargo(
                    persona=personas[o["persona"]],
                    cargo=cargos[o["cargo"]],
                    tipo=o["tipo"],
                    desde=_fecha(o["desde"]),
                    hasta=_fecha(o.get("hasta")),
                    acto_designacion=o.get("acto_designacion", ""),
                )
                nuevas += 1

        for pr in datos["procesos"]:
            Proceso.objects.update_or_create(
                codigo=pr["codigo"],
                defaults={
                    "nombre": pr["nombre"],
                    "requiere_proyecto": pr["requiere_proyecto"],
                    "plazo_dias_defecto": pr["plazo_dias_defecto"],
                },
            )

        instituciones: dict[str, InstitucionExterna] = {}
        for i in datos["instituciones"]:
            instituciones[i["codigo"]], _ = InstitucionExterna.objects.update_or_create(
                codigo=i["codigo"],
                defaults={k: v for k, v in i.items() if k != "codigo"},
            )

        for py in datos["proyectos"]:
            Proyecto.objects.update_or_create(
                codigo=py["codigo"],
                defaults={
                    "unidad": unidades[py["unidad"]],
                    "nombre": py["nombre"],
                    "tipo": py["tipo"],
                    "instituto": instituciones.get(py.get("instituto")),
                    "municipio": py.get("municipio", ""),
                    "contrato_ref": py.get("contrato_ref", ""),
                    "gestion_inicio": py.get("gestion_inicio"),
                    "presupuesto_bs": Decimal(py["presupuesto_bs"])
                    if py.get("presupuesto_bs")
                    else None,
                    "estado": py["estado"],
                    "cargo_fiscal": cargos.get(py.get("cargo_fiscal")),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Semillas cargadas: {len(unidades)} unidades, {len(cargos)} cargos, "
                f"{len(personas)} personas, {nuevas} ocupaciones nuevas."
            )
        )
