"""Matriz rol × acción × clasificación de `puede()` (docs/seguridad.md §2.3 y §4.3)."""

import datetime as dt
from dataclasses import dataclass, field

import pytest
from django.contrib.auth.models import AnonymousUser, Group, User

from apps.core import services as core_services
from apps.core.models import Cargo, Persona, Unidad
from apps.seguridad.permisos import Accion, Clasificacion, puede

pytestmark = pytest.mark.django_db

HOY = dt.date(2026, 1, 1)
C = Clasificacion


@dataclass
class Recurso:
    unidad_id: int | None
    clasificacion: str
    con_acceso: set[int] = field(default_factory=set)
    responsables: set[int] = field(default_factory=set)
    firmantes: set[int] = field(default_factory=set)

    def cargos_con_acceso(self):
        return self.con_acceso

    def cargos_responsables(self):
        return self.responsables

    def cargos_firmantes(self):
        return self.firmantes


@pytest.fixture
def escenario():
    u1 = Unidad.objects.create(sigla="U1", nombre="Unidad 1")
    u2 = Unidad.objects.create(sigla="U2", nombre="Unidad 2")
    cargos = {
        "dir": Cargo.objects.create(
            unidad=u1, codigo="U1-DIR", nombre="Director", puede_firmar=True
        ),
        "tec": Cargo.objects.create(unidad=u1, codigo="U1-TEC", nombre="Técnico"),
        "ven": Cargo.objects.create(
            unidad=u1, codigo="U1-VEN", nombre="Ventanilla", es_ventanilla=True
        ),
        "con": Cargo.objects.create(unidad=u1, codigo="U1-CON", nombre="Consulta"),
        "otro": Cargo.objects.create(unidad=u1, codigo="U1-OTRO", nombre="Sin rol"),
        "ext": Cargo.objects.create(unidad=u2, codigo="U2-TEC", nombre="Técnico U2"),
    }
    definicion = {
        "director": ("director", "dir"),
        "tecnico": ("tecnico", "tec"),
        "ventanilla": ("ventanilla", "ven"),
        "consulta": ("consulta", "con"),
        "auditor": ("auditor", None),
        "administrador": ("administrador", None),
        "sin_rol": (None, "otro"),
        "externo": ("tecnico", "ext"),
    }
    usuarios = {}
    for nombre, (rol, cargo) in definicion.items():
        usuario = User.objects.create_user(nombre, password="x")
        if rol:
            usuario.groups.add(Group.objects.get(name=rol))
        if cargo:
            persona = Persona.objects.create(nombres=nombre, apellidos="Prueba", usuario=usuario)
            core_services.asignar_cargo(
                persona=persona, cargo=cargos[cargo], tipo="titular", desde=HOY
            )
        usuarios[nombre] = User.objects.get(pk=usuario.pk)  # sin cachés
    return u1, cargos, usuarios


def recurso(u1, cargos, clasificacion):
    return Recurso(
        unidad_id=u1.pk,
        clasificacion=clasificacion,
        con_acceso={cargos["tec"].pk},
        responsables={cargos["tec"].pk},
        firmantes={cargos["dir"].pk},
    )


TODOS = [
    "director",
    "tecnico",
    "ventanilla",
    "consulta",
    "auditor",
    "administrador",
    "sin_rol",
    "externo",
]

# (acción, clasificación) -> usuarios que SÍ pueden. El resto no.
ESPERADO = {
    (Accion.VER, C.PUBLICO): set(TODOS),
    (Accion.VER, C.INTERNO): {
        "director",
        "tecnico",
        "ventanilla",
        "consulta",
        "auditor",
        "sin_rol",
    },
    (Accion.VER, C.CONFIDENCIAL): {"director", "tecnico", "auditor"},
    (Accion.VER, C.RESERVADO): {"tecnico"},
    (Accion.EDITAR, C.PUBLICO): {"director", "tecnico"},
    (Accion.EDITAR, C.INTERNO): {"director", "tecnico"},
    (Accion.EDITAR, C.CONFIDENCIAL): {"director", "tecnico"},
    (Accion.EDITAR, C.RESERVADO): {"tecnico"},
    (Accion.DERIVAR, C.PUBLICO): {"director", "tecnico"},
    (Accion.DERIVAR, C.INTERNO): {"director", "tecnico"},
    (Accion.DERIVAR, C.CONFIDENCIAL): {"director", "tecnico"},
    (Accion.DERIVAR, C.RESERVADO): {"tecnico"},
    (Accion.FIRMAR, C.PUBLICO): {"director"},
    (Accion.FIRMAR, C.INTERNO): {"director"},
    (Accion.FIRMAR, C.CONFIDENCIAL): {"director"},
    (Accion.FIRMAR, C.RESERVADO): set(),
    (Accion.ANULAR, C.PUBLICO): {"director"},
    (Accion.ANULAR, C.INTERNO): {"director"},
    (Accion.ANULAR, C.CONFIDENCIAL): {"director"},
    (Accion.ANULAR, C.RESERVADO): set(),
    (Accion.DESPACHAR, C.PUBLICO): {"ventanilla"},
    (Accion.DESPACHAR, C.INTERNO): {"ventanilla"},
    (Accion.DESPACHAR, C.CONFIDENCIAL): set(),
    (Accion.DESPACHAR, C.RESERVADO): set(),
}

ESPERADO_GLOBAL = {
    Accion.ADMINISTRAR_CATALOGOS: {"administrador"},
    Accion.GESTIONAR_USUARIOS: {"administrador"},
    Accion.VER_BITACORA: {"administrador", "auditor"},
    Accion.REGISTRAR_ENTRADA: {"ventanilla"},
}


@pytest.mark.parametrize(("accion", "clasificacion"), list(ESPERADO))
def test_matriz_sobre_objetos(escenario, accion, clasificacion):
    u1, cargos, usuarios = escenario
    objeto = recurso(u1, cargos, clasificacion)
    obtenido = {n for n in TODOS if puede(usuarios[n], accion, objeto)}
    assert obtenido == ESPERADO[(accion, clasificacion)]


@pytest.mark.parametrize("accion", list(ESPERADO_GLOBAL))
def test_matriz_global(escenario, accion):
    _, _, usuarios = escenario
    obtenido = {n for n in TODOS if puede(usuarios[n], accion)}
    assert obtenido == ESPERADO_GLOBAL[accion]


def test_niega_a_anonimo_inactivo_y_accion_desconocida(escenario):
    u1, cargos, usuarios = escenario
    objeto = recurso(u1, cargos, C.PUBLICO)
    assert not puede(AnonymousUser(), Accion.VER, objeto)
    assert not puede(None, Accion.VER, objeto)
    director = usuarios["director"]
    assert not puede(director, "borrar_todo", objeto)
    director.is_active = False
    assert not puede(director, Accion.VER, objeto)


def test_objeto_sin_protocolo_o_clasificacion_desconocida(escenario):
    u1, cargos, usuarios = escenario
    assert not puede(usuarios["director"], Accion.VER, object())
    assert not puede(usuarios["director"], Accion.VER, recurso(u1, cargos, "secreto_maximo"))
    assert not puede(usuarios["director"], Accion.EDITAR)  # acción sobre objeto sin objeto


def test_superusuario_puede_todo(escenario):
    u1, cargos, _ = escenario
    raiz = User.objects.create_superuser("raiz", password="x")
    assert puede(raiz, Accion.VER, recurso(u1, cargos, C.RESERVADO))
    assert puede(raiz, Accion.ADMINISTRAR_CATALOGOS)


def test_suplencia_da_permisos_solo_en_su_periodo(escenario):
    u1, cargos, usuarios = escenario
    tecnico = usuarios["tecnico"]
    tecnico.groups.add(Group.objects.get(name="director"))
    core_services.asignar_cargo(
        persona=tecnico.persona,
        cargo=cargos["dir"],
        tipo="suplente",
        desde=dt.date(2020, 1, 1),
        hasta=dt.date(2020, 1, 10),
    )
    objeto = Recurso(unidad_id=u1.pk, clasificacion=C.INTERNO, firmantes={cargos["dir"].pk})
    assert not puede(User.objects.get(pk=tecnico.pk), Accion.FIRMAR, objeto)  # suplencia vencida
