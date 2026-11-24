"""Datos ficticios para las pruebas del módulo de institutos."""

import datetime as dt

from django.contrib.auth.models import Group, User

from apps.core import services as core_services
from apps.core.models import Cargo, InstitucionExterna, Persona, Unidad
from apps.institutos.models import Instituto


def unidad_con_cargos(sigla="DDGS"):
    unidad = Unidad.objects.create(sigla=sigla, nombre=f"Unidad {sigla}")
    cargos = {
        "dir": Cargo.objects.create(
            unidad=unidad, codigo=f"{sigla}-DIR", nombre="Director", puede_firmar=True
        ),
        "tec": Cargo.objects.create(unidad=unidad, codigo=f"{sigla}-TEC", nombre="Técnico"),
        "ven": Cargo.objects.create(
            unidad=unidad, codigo=f"{sigla}-VEN", nombre="Ventanilla", es_ventanilla=True
        ),
    }
    return unidad, cargos


def usuario_con_cargo(nombre, rol, cargo):
    usuario = User.objects.create_user(nombre, password="Clave-de-prueba-larga-2026")
    if rol:
        usuario.groups.add(Group.objects.get(name=rol))
    if cargo is not None:
        persona = Persona.objects.create(nombres=nombre, apellidos="Prueba", usuario=usuario)
        core_services.asignar_cargo(
            persona=persona, cargo=cargo, tipo="titular", desde=dt.date(2026, 1, 1)
        )
    return User.objects.get(pk=usuario.pk)


def instituto(unidad, numero=1, nombre="Instituto Tecnológico Ejemplo", **extra):
    institucion = InstitucionExterna.objects.create(
        codigo=f"ITT-{numero:03d}", tipo="instituto", nombre=nombre
    )
    return Instituto.objects.create(
        institucion=institucion, unidad=unidad, numero=numero, nombre=nombre, **extra
    )
