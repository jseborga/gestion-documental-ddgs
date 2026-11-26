"""Lista, mapa, GeoJSON, ficha e importación de institutos. Todo acceso pasa por `puede()`."""

import logging
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.auditoria import selectors as bitacora_lectura
from apps.auditoria import services as bitacora
from apps.core.models import Proyecto
from apps.eventos import services as eventos
from apps.eventos.models import EventoOutbox
from apps.seguridad.permisos import Accion, puede
from apps.seguridad.red import ip_cliente

from . import importador, selectors, services
from .forms import FiltroForm, ImportarForm, UbicacionForm
from .models import Instituto
from .tareas import EVENTO_APROXIMAR

logger = logging.getLogger(__name__)

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
            "puede_importar": puede(request.user, Accion.ADMINISTRAR_CATALOGOS),
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


def _exigir_administrador(request) -> None:
    if not puede(request.user, Accion.ADMINISTRAR_CATALOGOS):
        raise PermissionDenied


def _guardar_temporal(archivo, carpeta: Path, nombre: str) -> Path:
    """Escribe la subida con un nombre generado por el servidor (nunca el del cliente)."""
    ruta = carpeta / nombre
    with ruta.open("wb") as destino:
        for bloque in archivo.chunks():
            destino.write(bloque)
    return ruta


@login_required
@require_http_methods(["GET", "POST"])
def importar(request):
    _exigir_administrador(request)
    informe = None
    form = ImportarForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with tempfile.TemporaryDirectory(prefix="importacion-") as carpeta:
            carpeta = Path(carpeta)
            try:
                datos = _guardar_temporal(form.cleaned_data["datos"], carpeta, "datos.xlsx")
                ficha = _guardar_temporal(form.cleaned_data["ficha"], carpeta, "ficha.xlsx")
                extra = []
                if form.cleaned_data["observaciones"]:
                    csv = _guardar_temporal(form.cleaned_data["observaciones"], carpeta, "obs.csv")
                    extra = importador.leer_observaciones_csv(csv)
                lectura = importador.leer(datos, ficha, extra)
                informe = services.importar(
                    lectura=lectura,
                    unidad=form.cleaned_data["unidad"],
                    actor=request.user,
                    simular=form.cleaned_data["simular"],
                )
            except importador.ArchivoNoValido as error:
                form.add_error(None, str(error))
            except Exception:
                logger.exception("Error al importar planillas de institutos")
                form.add_error(
                    None,
                    "No se pudo procesar el archivo. Verifique que sea la planilla correcta "
                    "(formato v1) o use la importación por comando para ver el detalle.",
                )
    ultima_aproximacion = bitacora_lectura.ultimo_de(
        ["ubicaciones_aproximadas", "ubicaciones_aproximadas_error"]
    )
    detalle = (ultima_aproximacion.despues or {}) if ultima_aproximacion else {}
    return render(
        request,
        "institutos/importar.html",
        {
            "ultima_aproximacion_texto": detalle.get("resumen") or detalle.get("error", ""),
            "form": form,
            "informe": informe,
            "ultima_importacion": bitacora_lectura.ultimo("institutos_importados"),
            "ultima_aproximacion": bitacora_lectura.ultimo_de(
                ["ubicaciones_aproximadas", "ubicaciones_aproximadas_error"]
            ),
            "aproximacion_en_curso": EventoOutbox.objects.filter(
                tipo=EVENTO_APROXIMAR, procesado_en__isnull=True, intentos__lt=5
            ).exists(),
            "sin_ubicacion": Instituto.objects.filter(lat__isnull=True).count(),
            "contacto_configurado": bool(settings.NOMINATIM_CONTACTO),
        },
    )


@login_required
@require_http_methods(["POST"])
def solicitar_aproximacion(request):
    _exigir_administrador(request)
    if EventoOutbox.objects.filter(
        tipo=EVENTO_APROXIMAR, procesado_en__isnull=True, intentos__lt=5
    ).exists():
        messages.warning(request, "Ya hay una solicitud en curso. Espere a que termine.")
        return redirect("institutos:importar")
    with transaction.atomic():
        eventos.publicar(
            tipo=EVENTO_APROXIMAR,
            agregado="institutos",
            agregado_id="ubicaciones",
            payload={"usuario": request.user.get_username(), "maximo": 100},
        )
        bitacora.registrar(
            accion="aproximacion_solicitada",
            actor=request.user,
            objeto_tipo="institutos",
            objeto_id="ubicaciones",
            ip=ip_cliente(request),
        )
    messages.success(
        request,
        "Solicitud registrada. Se procesa en segundo plano (aprox. 1 segundo por municipio); "
        "recargue esta página en unos minutos.",
    )
    return redirect("institutos:importar")
