"""Único punto de escritura de la bitácora."""

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .models import Bitacora

# Campos que nunca se guardan en la bitácora aunque formen parte de un objeto.
CAMPOS_SENSIBLES = {"password", "contrasena", "clave", "token", "secreto", "secret_key", "key"}


def _limpiar(datos: dict[str, Any] | None) -> dict[str, Any] | None:
    if datos is None:
        return None
    limpio = {k: ("***" if k.lower() in CAMPOS_SENSIBLES else v) for k, v in datos.items()}
    # Normaliza fechas, decimales, etc. a tipos JSON.
    return json.loads(json.dumps(limpio, cls=DjangoJSONEncoder))


def instantanea(objeto: models.Model, campos: list[str] | None = None) -> dict[str, Any]:
    """Valores de los campos concretos de un modelo, para `antes`/`despues`."""
    datos = {}
    for campo in objeto._meta.concrete_fields:
        if campos is not None and campo.name not in campos:
            continue
        datos[campo.attname] = getattr(objeto, campo.attname)
    return _limpiar(datos)


def registrar(
    *,
    accion: str,
    actor=None,
    objeto: models.Model | None = None,
    objeto_tipo: str = "",
    objeto_id: str | int = "",
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
    ip: str | None = None,
    categoria: str = Bitacora.Categoria.NEGOCIO,
) -> Bitacora:
    """Agrega un registro. Debe llamarse dentro de la misma transacción que el cambio."""
    if objeto is not None:
        objeto_tipo = objeto_tipo or objeto._meta.label_lower
        objeto_id = objeto_id or objeto.pk
    actor_valido = actor if getattr(actor, "is_authenticated", False) else None
    return Bitacora.objects.create(
        categoria=categoria,
        actor=actor_valido,
        actor_nombre=actor_valido.get_username() if actor_valido else "",
        accion=accion,
        objeto_tipo=objeto_tipo,
        objeto_id=str(objeto_id) if objeto_id != "" else "",
        antes=_limpiar(antes),
        despues=_limpiar(despues),
        ip=ip,
    )


def registrar_seguridad(**kwargs) -> Bitacora:
    return registrar(categoria=Bitacora.Categoria.SEGURIDAD, **kwargs)
