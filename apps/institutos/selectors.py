"""Consultas del módulo de institutos. La visibilidad replica `puede(VER)` en SQL."""

from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Subquery, Sum

from apps.core.models import Proyecto
from apps.seguridad.permisos import Clasificacion, contexto
from apps.seguridad.roles import Rol

from .models import DerechoPropietario, Instituto, Matricula

SEMAFORO = {
    "rojo": "Obra paralizada",
    "ambar": "Obra en ejecución o sin cierre financiero",
    "gris": "Derecho propietario pendiente",
    "verde": "Sin pendientes registrados",
}


def visibles_para(usuario) -> QuerySet[Instituto]:
    """Institutos que el usuario puede ver; equivalente a filtrar con puede(usuario, VER)."""
    base = Instituto.objects.all()
    if not getattr(usuario, "is_authenticated", False) or not usuario.is_active:
        return base.none()
    if usuario.is_superuser:
        return base
    ctx = contexto(usuario)
    if Rol.AUDITOR in ctx.roles:
        return base.exclude(clasificacion=Clasificacion.RESERVADO)
    condicion = Q(pk__in=[])
    if ctx.roles or ctx.cargos:
        condicion |= Q(clasificacion=Clasificacion.PUBLICO)
    condicion |= Q(clasificacion=Clasificacion.INTERNO, unidad_id__in=ctx.unidades)
    if Rol.DIRECTOR in ctx.roles:
        condicion |= Q(clasificacion=Clasificacion.CONFIDENCIAL, unidad_id__in=ctx.unidades_firma)
    return base.filter(condicion)


def con_indicadores(consulta: QuerySet[Instituto]) -> QuerySet[Instituto]:
    proyectos = Proyecto.objects.filter(instituto=OuterRef("institucion"))
    ultima_matricula = Matricula.objects.filter(instituto=OuterRef("pk")).order_by("-anio", "-mes")
    return consulta.select_related("derecho_propietario").annotate(
        n_proyectos=Count("institucion__proyectos", distinct=True),
        inversion_bs=Sum("institucion__proyectos__presupuesto_bs"),
        tiene_paralizada=Exists(proyectos.filter(estado=Proyecto.Estado.PARALIZADA)),
        tiene_en_curso=Exists(
            proyectos.filter(
                estado__in=[Proyecto.Estado.EN_EJECUCION, Proyecto.Estado.SIN_CIERRE_FINANCIERO]
            )
        ),
        estudiantes=Subquery(ultima_matricula.values("estudiantes")[:1]),
    )


def semaforo(instituto: Instituto) -> str:
    """Color según la situación más crítica (docs/modulo-institutos.md §4)."""
    if getattr(instituto, "tiene_paralizada", False):
        return "rojo"
    if getattr(instituto, "tiene_en_curso", False):
        return "ambar"
    derecho = getattr(instituto, "derecho_propietario", None) if _tiene_derecho(instituto) else None
    if derecho is None or derecho.estado != DerechoPropietario.Estado.A_NOMBRE_ENTIDAD:
        return "gris"
    return "verde"


def _tiene_derecho(instituto: Instituto) -> bool:
    try:
        instituto.derecho_propietario  # noqa: B018
    except DerechoPropietario.DoesNotExist:
        return False
    return True


def filtrar(consulta: QuerySet[Instituto], datos: dict) -> QuerySet[Instituto]:
    if datos.get("q"):
        consulta = consulta.filter(
            Q(nombre__icontains=datos["q"]) | Q(municipio__icontains=datos["q"])
        )
    for campo in ("region", "provincia", "municipio"):
        if datos.get(campo):
            consulta = consulta.filter(**{campo: datos[campo]})
    if datos.get("derecho"):
        consulta = consulta.filter(derecho_propietario__estado=datos["derecho"])
    if datos.get("sin_ubicacion"):
        consulta = consulta.filter(lat__isnull=True)
    estado = datos.get("estado")
    if estado == "rojo":
        consulta = consulta.filter(tiene_paralizada=True)
    elif estado == "ambar":
        consulta = consulta.filter(tiene_paralizada=False, tiene_en_curso=True)
    elif estado in ("gris", "verde"):
        consulta = consulta.filter(tiene_paralizada=False, tiene_en_curso=False)
        apto = Q(derecho_propietario__estado=DerechoPropietario.Estado.A_NOMBRE_ENTIDAD)
        consulta = consulta.filter(apto) if estado == "verde" else consulta.exclude(apto)
    return consulta


def opciones(consulta: QuerySet[Instituto], campo: str) -> list[str]:
    return list(
        consulta.exclude(**{campo: ""}).order_by(campo).values_list(campo, flat=True).distinct()
    )


def geojson(consulta: QuerySet[Instituto]) -> dict:
    """FeatureCollection SIN datos personales: ni autoridades ni teléfonos."""
    caracteristicas = []
    for inst in con_indicadores(consulta.filter(lat__isnull=False, lon__isnull=False)):
        caracteristicas.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(inst.lon), float(inst.lat)]},
                "properties": {
                    "id": inst.pk,
                    "numero": inst.numero,
                    "nombre": inst.nombre,
                    "region": inst.region,
                    "provincia": inst.provincia,
                    "municipio": inst.municipio,
                    "estado": semaforo(inst),
                    "precision": inst.precision,
                    "url": f"/institutos/{inst.pk}/",
                },
            }
        )
    return {"type": "FeatureCollection", "features": caracteristicas}
