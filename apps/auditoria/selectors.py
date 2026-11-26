import datetime as dt

from django.db.models import QuerySet
from django.utils import timezone

from .models import Bitacora


def historial_de(objeto_tipo: str, objeto_id: str | int) -> QuerySet[Bitacora]:
    return Bitacora.objects.filter(objeto_tipo=objeto_tipo, objeto_id=str(objeto_id))


def contar_recientes(accion: str, minutos: int, categoria: str | None = None) -> int:
    desde = timezone.now() - dt.timedelta(minutes=minutos)
    consulta = Bitacora.objects.filter(accion=accion, creado_en__gte=desde)
    if categoria:
        consulta = consulta.filter(categoria=categoria)
    return consulta.count()


def ultimo(accion: str) -> Bitacora | None:
    return Bitacora.objects.filter(accion=accion).order_by("-creado_en", "-id").first()


def ultimo_de(acciones: list[str]) -> Bitacora | None:
    return Bitacora.objects.filter(accion__in=acciones).order_by("-creado_en", "-id").first()
