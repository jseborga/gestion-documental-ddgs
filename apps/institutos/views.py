"""Lista, mapa, GeoJSON y ficha de institutos. Todo acceso pasa por `puede()`."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.models import Proyecto
from apps.seguridad.permisos import Accion, puede
from apps.seguridad.red import ip_cliente

from . import selectors, services
from .forms import FiltroForm, UbicacionForm
from .models import Instituto

POR_PAGINA = 50


def _filtros(request, visibles):
    form = FiltroForm(
        request.GET or None,
        regiones=selectors.opciones(visibles, "region"),
        provincias=selectors.opciones(visibles, "provincia"),
    )
    datos = form.cleaned_data if form.is_valid() else {}
    return form, datos


@login_required
@require_GET
def lista(request):
    visibles = selectors.visibles_para(request.user)
    form, datos = _filtros(request, visibles)
    consulta = selectors.filtrar(selectors.con_indicadores(visibles), datos).order_by(
        "numero", "nombre"
    )
    pagina = Paginator(consulta, POR_PAGINA).get_page(request.GET.get("pagina"))
    for inst in pagina:
        inst.color = selectors.semaforo(inst)
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(
        request,
        "institutos/lista.html",
        {
            "form": form,
            "pagina": pagina,
            "total": consulta.count(),
            "semaforo": selectors.SEMAFORO,
            "parametros": parametros.urlencode(),
        },
    )


@login_required
@require_GET
def mapa(request):
    visibles = selectors.visibles_para(request.user)
    form, datos = _filtros(request, visibles)
    consulta = selectors.filtrar(selectors.con_indicadores(visibles), datos)
    return render(
        request,
        "institutos/mapa.html",
        {
            "form": form,
            "sin_ubicar": consulta.filter(lat__isnull=True).order_by("numero")[:200],
            "con_ubicacion": consulta.filter(lat__isnull=False).count(),
            "teselas": settings.MAPA_TESELAS_URL,
            "atribucion": settings.MAPA_TESELAS_ATRIBUCION,
            "parametros": request.GET.urlencode(),
            "semaforo": selectors.SEMAFORO,
        },
    )


@login_required
@require_GET
def geojson(request):
    visibles = selectors.visibles_para(request.user)
    _, datos = _filtros(request, visibles)
    consulta = selectors.filtrar(selectors.con_indicadores(visibles), datos)
    return JsonResponse(selectors.geojson(consulta))


def _instituto_visible(request, pk) -> Instituto:
    instituto = get_object_or_404(Instituto.objects.select_related("unidad"), pk=pk)
    if not puede(request.user, Accion.VER, instituto):
        raise PermissionDenied
    return instituto


@login_required
@require_GET
def ficha(request, pk):
    instituto = _instituto_visible(request, pk)
    anotado = selectors.con_indicadores(Instituto.objects.filter(pk=pk)).first()
    puede_editar = puede(request.user, Accion.EDITAR, instituto)
    proyectos = Proyecto.objects.filter(instituto=instituto.institucion).order_by(
        "-gestion_inicio", "tipo"
    )
    return render(
        request,
        "institutos/ficha.html",
        {
            "inst": instituto,
            "color": selectors.semaforo(anotado),
            "estado_texto": selectors.SEMAFORO[selectors.semaforo(anotado)],
            "teselas": settings.MAPA_TESELAS_URL,
            "anotado": anotado,
            "semaforo": selectors.SEMAFORO,
            "proyectos": proyectos,
            "puede_editar": puede_editar,
            # Datos personales solo para quien opera la unidad.
            "autoridades": instituto.autoridades.filter(vigente=True) if puede_editar else None,
            "derecho": getattr(instituto, "derecho_propietario", None)
            if selectors._tiene_derecho(instituto)
            else None,
            "ubicaciones": instituto.ubicaciones.select_related("registrado_por")[:10],
            "observaciones": instituto.observaciones.all(),
            "form_ubicacion": UbicacionForm() if puede_editar else None,
        },
    )


@login_required
@require_http_methods(["POST"])
def registrar_ubicacion(request, pk):
    instituto = _instituto_visible(request, pk)
    if not puede(request.user, Accion.EDITAR, instituto):
        raise PermissionDenied
    form = UbicacionForm(request.POST)
    if form.is_valid():
        try:
            lat, lon = services.parsear_coordenadas(form.cleaned_data["coordenadas"])
            services.registrar_ubicacion(
                instituto=instituto,
                lat=lat,
                lon=lon,
                precision=form.cleaned_data["precision"],
                fuente=form.cleaned_data["fuente"],
                actor=request.user,
                ip=ip_cliente(request),
            )
            messages.success(request, "Ubicación registrada.")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
    else:
        messages.error(request, "Revise los datos de la ubicación.")
    return redirect(f"/institutos/{instituto.pk}/#ubicacion")
