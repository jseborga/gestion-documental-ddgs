"""Roles del sistema (SPEC.md §7). Son grupos de Django creados por migración."""

from enum import StrEnum

from django.conf import settings


class Rol(StrEnum):
    ADMINISTRADOR = "administrador"
    DIRECTOR = "director"
    VENTANILLA = "ventanilla"
    TECNICO = "tecnico"
    CONSULTA = "consulta"
    AUDITOR = "auditor"


def roles_de(usuario) -> set[str]:
    if not getattr(usuario, "is_authenticated", False):
        return set()
    if not hasattr(usuario, "_roles_cache"):
        usuario._roles_cache = set(usuario.groups.values_list("name", flat=True))
    return usuario._roles_cache


def requiere_segundo_factor(usuario) -> bool:
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser or settings.MFA_OBLIGATORIO_TODOS:
        return True
    return bool(roles_de(usuario) & set(settings.MFA_OBLIGATORIO_ROLES))
