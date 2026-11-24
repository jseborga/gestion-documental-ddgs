import json
import re
from decimal import Decimal

import pytest

from apps.core.models import Proyecto
from apps.institutos import selectors, services
from apps.institutos.models import AutoridadInstituto, DerechoPropietario, Instituto, Precision
from apps.seguridad.permisos import Accion, puede

from .conftest import verificar_cliente
from .institutos_util import instituto, unidad_con_cargos, usuario_con_cargo

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    unidad, cargos = unidad_con_cargos()
    otra, cargos_otra = unidad_con_cargos("OTRA")
    alfa = instituto(
        unidad, 1, "Instituto Alfa", region="Altiplano", provincia="Uno", municipio="A"
    )
    beta = instituto(unidad, 2, "Instituto <script>alert(1)</script> Beta", region="Valles")
    ajeno = instituto(otra, 3, "Instituto de otra unidad")
    AutoridadInstituto.objects.create(instituto=alfa, nombre="Persona Secreta", telefono="70011122")
    DerechoPropietario.objects.create(instituto=alfa, estado="a_nombre_entidad")
    services.registrar_ubicacion(
        instituto=alfa, lat=Decimal("-16.5"), lon=Decimal("-68.15"), precision=Precision.GPS_SITIO
    )
    Proyecto.objects.create(
        unidad=unidad, codigo="P-1", nombre="Obra", instituto=beta.institucion, estado="paralizada"
    )
    usuarios = {
        "director": usuario_con_cargo("dir", "director", cargos["dir"]),
        "tecnico": usuario_con_cargo("tec", "tecnico", cargos["tec"]),
        "ventanilla": usuario_con_cargo("ven", "ventanilla", cargos["ven"]),
        "externo": usuario_con_cargo("ext", "tecnico", cargos_otra["tec"]),
        "auditor": usuario_con_cargo("aud", "auditor", None),
        "sin_nada": usuario_con_cargo("nada", None, None),
    }
    return {"alfa": alfa, "beta": beta, "ajeno": ajeno, "usuarios": usuarios}


def cliente(client, escenario, nombre):
    return verificar_cliente(client, escenario["usuarios"][nombre])


def test_visibilidad_sql_coincide_con_puede(escenario):
    todos = list(Instituto.objects.all())
    for usuario in escenario["usuarios"].values():
        esperado = {i.pk for i in todos if puede(usuario, Accion.VER, i)}
        assert set(selectors.visibles_para(usuario).values_list("pk", flat=True)) == esperado


def test_anonimo_redirige(client):
    for url in ("/institutos/", "/institutos/mapa/", "/institutos/geojson/", "/institutos/1/"):
        respuesta = client.get(url)
        assert respuesta.status_code == 302 and "/seguridad/entrar/" in respuesta["Location"]


def test_lista_solo_de_su_unidad_y_escapada(client, escenario):
    respuesta = cliente(client, escenario, "tecnico").get("/institutos/")
    html = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Instituto Alfa" in html and "Instituto de otra unidad" not in html
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert not re.search(r"<script>(?!\s*$)", html.split("</main>")[0])  # sin scripts en línea


def test_filtro_por_situacion(client, escenario):
    html = cliente(client, escenario, "tecnico").get("/institutos/?estado=rojo").content.decode()
    assert "Beta" in html and "Instituto Alfa" not in html
    html = client.get("/institutos/?estado=verde").content.decode()
    assert "Instituto Alfa" in html and "Beta" not in html


def test_filtro_invalido_no_rompe(client, escenario):
    respuesta = cliente(client, escenario, "tecnico").get(
        "/institutos/?estado=x&region=<b>&pagina=999"
    )
    assert respuesta.status_code == 200


def test_geojson_sin_datos_personales(client, escenario):
    respuesta = cliente(client, escenario, "tecnico").get("/institutos/geojson/")
    datos = respuesta.json()
    assert [f["properties"]["nombre"] for f in datos["features"]] == ["Instituto Alfa"]
    texto = json.dumps(datos)
    assert "70011122" not in texto and "Persona Secreta" not in texto
    assert datos["features"][0]["geometry"]["coordinates"] == [-68.15, -16.5]


def test_geojson_de_otra_unidad_vacio(client, escenario):
    assert (
        cliente(client, escenario, "externo").get("/institutos/geojson/").json()["features"] == []
    )


def test_ficha_permisos_y_datos_personales(client, escenario):
    alfa = escenario["alfa"]
    html = cliente(client, escenario, "tecnico").get(f"/institutos/{alfa.pk}/").content.decode()
    assert "70011122" in html and "Registrar ubicación" in html
    client.logout()
    html = cliente(client, escenario, "ventanilla").get(f"/institutos/{alfa.pk}/").content.decode()
    assert "Instituto Alfa" in html and "70011122" not in html and "Persona Secreta" not in html
    assert "Registrar ubicación" not in html
    client.logout()
    assert cliente(client, escenario, "externo").get(f"/institutos/{alfa.pk}/").status_code == 403
    assert client.get("/institutos/999999/").status_code == 404


def test_registrar_ubicacion_permisos(client, escenario):
    beta = escenario["beta"]
    url = f"/institutos/{beta.pk}/ubicacion/"
    datos = {"coordenadas": "-16.6, -68.2", "precision": "verificada_mapa", "fuente": "prueba"}
    assert cliente(client, escenario, "ventanilla").post(url, datos).status_code == 403
    client.logout()
    assert cliente(client, escenario, "externo").post(url, datos).status_code == 403
    client.logout()
    tecnico = cliente(client, escenario, "tecnico")
    assert tecnico.get(url).status_code == 405
    assert tecnico.post(url, datos).status_code == 302
    beta.refresh_from_db()
    assert (beta.lat, beta.lon) == (Decimal("-16.600000"), Decimal("-68.200000"))


def test_registrar_ubicacion_errores_visibles(client, escenario):
    beta = escenario["beta"]
    tecnico = cliente(client, escenario, "tecnico")
    respuesta = tecnico.post(
        f"/institutos/{beta.pk}/ubicacion/",
        {"coordenadas": "https://maps.app.goo.gl/abc", "precision": "verificada_mapa"},
        follow=True,
    )
    assert "enlaces cortos" in respuesta.content.decode()
    beta.refresh_from_db()
    assert beta.lat is None


def test_mapa_carga_leaflet_local_y_csp(client, escenario):
    respuesta = cliente(client, escenario, "tecnico").get("/institutos/mapa/")
    html = respuesta.content.decode()
    assert "/static/vendor/leaflet/leaflet.js" in html and "unpkg" not in html and "cdn" not in html
    assert "script-src 'self'" in respuesta["Content-Security-Policy"]
    assert "Beta" in html  # aparece en la lista de sin ubicación
