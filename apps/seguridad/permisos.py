"""Autorización centralizada: `puede(usuario, accion, objeto)` (docs/seguridad.md §2.3).

Ninguna vista ni plantilla decide permisos por su cuenta. Combina rol (grupo) con
atributos: cargos vigentes del usuario (incluidas suplencias), unidad y clasificación
del objeto, y los cargos que el propio objeto declara autorizados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from apps.core import selectors as core_selectors

from .roles import Rol, roles_de


class Accion(StrEnum):
    # Globales (sin objeto)
    ADMINISTRAR_CATALOGOS = "administrar_catalogos"
    GESTIONAR_USUARIOS = "gestionar_usuarios"
    VER_BITACORA = "ver_bitacora"
    REGISTRAR_ENTRADA = "registrar_entrada"
    # Sobre un objeto protegido
    VER = "ver"
    EDITAR = "editar"
    DERIVAR = "derivar"
    FIRMAR = "firmar"
    ANULAR = "anular"
    DESPACHAR = "despachar"


ACCIONES_GLOBALES = {
    Accion.ADMINISTRAR_CATALOGOS,
    Accion.GESTIONAR_USUARIOS,
    Accion.VER_BITACORA,
    Accion.REGISTRAR_ENTRADA,
}


class Clasificacion(StrEnum):
    PUBLICO = "publico"
    INTERNO = "interno"
    CONFIDENCIAL = "confidencial"
    RESERVADO = "reservado"


@runtime_checkable
class RecursoProtegido(Protocol):
    """Lo que un objeto (expediente, documento, ficha…) debe exponer para `puede()`."""

    unidad_id: int | None
    clasificacion: str

    def cargos_con_acceso(self) -> set[int]:
        """Cargos derivados o de la lista explícita (confidencial/reservado)."""

    def cargos_responsables(self) -> set[int]:
        """Cargos que hoy tienen el trámite a su cargo (editan y derivan)."""

    def cargos_firmantes(self) -> set[int]:
        """Cargos que deben firmar el documento."""


@dataclass
class Contexto:
    roles: set[str]
    cargos: set[int] = field(default_factory=set)
    cargos_firma: set[int] = field(default_factory=set)
    cargos_ventanilla: set[int] = field(default_factory=set)
    unidades_ventanilla: set[int] = field(default_factory=set)
    unidades: set[int] = field(default_factory=set)
    unidades_firma: set[int] = field(default_factory=set)


def contexto(usuario) -> Contexto:
    """Roles y cargos vigentes del usuario; se calcula una vez por petición."""
    if hasattr(usuario, "_contexto_permisos"):
        return usuario._contexto_permisos
    ctx = Contexto(roles=roles_de(usuario))
    persona = getattr(usuario, "persona", None) if usuario.pk else None
    if persona is not None and persona.activo:
        for cargo in core_selectors.cargos_vigentes(persona):
            ctx.cargos.add(cargo.pk)
            ctx.unidades.add(cargo.unidad_id)
            if cargo.puede_firmar:
                ctx.cargos_firma.add(cargo.pk)
                ctx.unidades_firma.add(cargo.unidad_id)
            if cargo.es_ventanilla:
                ctx.cargos_ventanilla.add(cargo.pk)
                ctx.unidades_ventanilla.add(cargo.unidad_id)
    usuario._contexto_permisos = ctx
    return ctx


def _es_director_de(ctx: Contexto, unidad_id: int | None) -> bool:
    return Rol.DIRECTOR in ctx.roles and unidad_id in ctx.unidades_firma


def _puede_ver(ctx: Contexto, objeto: RecursoProtegido) -> bool:
    clasificacion = objeto.clasificacion
    con_acceso = objeto.cargos_con_acceso()
    if clasificacion == Clasificacion.RESERVADO:
        # Solo la lista explícita; ni el auditor ni el director ven sin estar en ella.
        return bool(ctx.cargos & con_acceso)
    if Rol.AUDITOR in ctx.roles:
        return True
    if clasificacion == Clasificacion.PUBLICO:
        return bool(ctx.roles or ctx.cargos)
    if clasificacion == Clasificacion.INTERNO:
        return objeto.unidad_id in ctx.unidades or bool(ctx.cargos & con_acceso)
    if clasificacion == Clasificacion.CONFIDENCIAL:
        return _es_director_de(ctx, objeto.unidad_id) or bool(ctx.cargos & con_acceso)
    return False  # clasificación desconocida: se niega


ROLES_SOLO_LECTURA = {Rol.AUDITOR, Rol.CONSULTA}
ROLES_OPERATIVOS = {Rol.DIRECTOR, Rol.TECNICO, Rol.VENTANILLA}


def _puede_escribir(ctx: Contexto) -> bool:
    # Quien tenga un rol operativo puede escribir aunque además sea auditor o consulta.
    return bool(ctx.roles & ROLES_OPERATIVOS)


def puede(usuario, accion: str, objeto: RecursoProtegido | None = None) -> bool:
    """¿El usuario puede realizar la acción (sobre el objeto)? Niega por defecto."""
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    if not usuario.is_active:
        return False
    try:
        accion = Accion(accion)
    except ValueError:
        return False
    if usuario.is_superuser:
        return True  # solo emergencias; su uso se alerta al iniciar sesión
    ctx = contexto(usuario)

    if accion in ACCIONES_GLOBALES:
        if accion in (Accion.ADMINISTRAR_CATALOGOS, Accion.GESTIONAR_USUARIOS):
            return Rol.ADMINISTRADOR in ctx.roles
        if accion == Accion.VER_BITACORA:
            return bool(ctx.roles & {Rol.ADMINISTRADOR, Rol.AUDITOR})
        if accion == Accion.REGISTRAR_ENTRADA:
            return Rol.VENTANILLA in ctx.roles and bool(ctx.cargos_ventanilla)
        return False

    if objeto is None or not isinstance(objeto, RecursoProtegido):
        return False
    if not _puede_ver(ctx, objeto):
        return False
    if accion == Accion.VER:
        return True
    if not _puede_escribir(ctx):
        return False

    director = _es_director_de(ctx, objeto.unidad_id)
    responsables = objeto.cargos_responsables()
    if accion in (Accion.EDITAR, Accion.DERIVAR):
        return director or bool(ctx.cargos & responsables)
    if accion == Accion.FIRMAR:
        return bool(ctx.cargos & objeto.cargos_firmantes())
    if accion == Accion.ANULAR:
        return director or bool(ctx.cargos_firma & objeto.cargos_firmantes())
    if accion == Accion.DESPACHAR:
        return Rol.VENTANILLA in ctx.roles and objeto.unidad_id in ctx.unidades_ventanilla
    return False
