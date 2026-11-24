import zipfile
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.auditoria.models import Bitacora
from apps.core.models import Proyecto
from apps.institutos import importador, services
from apps.institutos.models import (
    AutoridadInstituto,
    Carrera,
    DerechoPropietario,
    Instituto,
    Matricula,
    ObservacionDato,
    TechoPresupuestario,
)

from .institutos_util import unidad_con_cargos
from .planillas_sinteticas import crear_datos, crear_ficha

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def patrones_titular(settings):
    settings.INSTITUTOS_TITULAR_PATRONES = ["gobierno autonomo"]


@pytest.fixture
def planillas(tmp_path):
    return crear_datos(tmp_path / "datos.xlsx"), crear_ficha(tmp_path / "ficha.xlsx")


@pytest.fixture
def unidad():
    return unidad_con_cargos()[0]


class TestLectura:
    def test_lee_institutos_y_proyectos(self, planillas):
        lectura = importador.leer(*planillas)
        assert sorted(lectura.institutos) == [1, 2, 3]
        alfa = lectura.institutos[1]
        assert [p.estado for p in alfa.proyectos] == ["en_ejecucion", "paralizada"]
        assert alfa.proyectos[0].presupuesto_bs == Decimal("1500000.50")
        assert (alfa.proyectos[0].gestion_inicio, alfa.proyectos[0].gestion_fin) == (2022, 2024)
        beta = lectura.institutos[2]
        assert beta.es_subsede
        equipamiento = [p for p in beta.proyectos if p.tipo == "equipamiento"]
        assert [(p.gestion_inicio, p.estado, p.presupuesto_bs) for p in equipamiento] == [
            (2024, "concluida", Decimal("350000.00")),
            (2026, "programado", Decimal("90000.00")),
        ]
        assert (lectura.matricula_anio, lectura.matricula_mes, lectura.techo_gestion) == (
            2026,
            7,
            2026,
        )

    def test_ficha_y_estados_de_derecho_propietario(self, planillas):
        lectura = importador.leer(*planillas)
        estados = {n: i.derecho_estado for n, i in lectura.institutos.items()}
        assert estados == {
            1: "a_nombre_entidad",
            2: "en_proceso_con_folio",
            3: "en_proceso_sin_antecedentes",
        }
        assert lectura.institutos[1].carreras == ["Mecánica Automotriz", "Contaduría"]
        assert lectura.institutos[2].resolucion_anio == 2009

    def test_observaciones(self, planillas):
        textos = " | ".join(t for _, t in importador.leer(*planillas).observaciones)
        for esperado in (
            "gestiones de equipamiento están escritas en una fila de datos",
            "Folio real 2.01.0.99.000001 repetido",
            "Nombre distinto entre archivos",
            "Estudiantes distintos entre archivos: 120 / 130",
            "Techo presupuestario sin monto legible",
            "El N° 99 aparece en la ficha técnica pero no en la planilla de datos",
            "Proyecto sin presupuesto legible: OBRA SIN MONTO",
        ):
            assert esperado in textos, esperado


class TestArchivosNoValidos:
    def test_extension(self, tmp_path):
        ruta = tmp_path / "datos.xls"
        ruta.write_bytes(b"x")
        with pytest.raises(importador.ArchivoNoValido, match="solo se aceptan"):
            importador.validar_archivo(ruta)

    def test_contenido_falso(self, tmp_path):
        ruta = tmp_path / "datos.xlsx"
        ruta.write_text("<html>no soy un excel</html>")
        with pytest.raises(importador.ArchivoNoValido, match="no es un libro"):
            importador.validar_archivo(ruta)

    def test_con_macros(self, tmp_path, planillas):
        ruta = tmp_path / "macros.xlsx"
        with zipfile.ZipFile(planillas[0]) as origen, zipfile.ZipFile(ruta, "w") as destino:
            for entrada in origen.infolist():
                destino.writestr(entrada, origen.read(entrada))
            destino.writestr("xl/vbaProject.bin", b"macro")
        with pytest.raises(importador.ArchivoNoValido, match="macros"):
            importador.validar_archivo(ruta)

    def test_bomba_de_compresion(self, tmp_path):
        ruta = tmp_path / "bomba.xlsx"
        with zipfile.ZipFile(ruta, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/relleno.xml", b"0" * (importador.MAX_DESCOMPRIMIDO + 1))
        with pytest.raises(importador.ArchivoNoValido, match="demasiado grande"):
            importador.validar_archivo(ruta)

    @override_settings(IMPORTACION_MAX_MB=0)
    def test_tamano(self, planillas):
        with pytest.raises(importador.ArchivoNoValido, match="supera"):
            importador.validar_archivo(planillas[0])

    def test_sin_encabezados(self, tmp_path):
        ruta = crear_datos(tmp_path / "d.xlsx", filas=[])
        import openpyxl

        libro = openpyxl.load_workbook(ruta)
        libro.active.delete_rows(4)
        libro.save(ruta)
        with pytest.raises(importador.ArchivoNoValido, match="encabezados"):
            importador.leer_datos(ruta, [])


class TestImportacion:
    def test_simulacion_no_guarda_nada(self, planillas, unidad):
        informe = services.importar(
            lectura=importador.leer(*planillas), unidad=unidad, simular=True
        )
        assert informe.institutos_nuevos == 3 and informe.simulacion
        assert not Instituto.objects.exists() and not Proyecto.objects.exists()
        assert not Bitacora.objects.filter(accion="institutos_importados").exists()

    def test_importa_todo(self, planillas, unidad):
        informe = services.importar(lectura=importador.leer(*planillas), unidad=unidad)
        assert (informe.institutos_nuevos, informe.proyectos) == (3, 6)
        alfa = Instituto.objects.get(numero=1)
        assert alfa.dependencia == "fiscal" and alfa.unidad == unidad
        assert Instituto.objects.get(numero=2).dependencia == "convenio"
        assert Proyecto.objects.filter(instituto=alfa.institucion, estado="paralizada").count() == 1
        assert Matricula.objects.get(instituto=alfa).estudiantes == 350
        assert TechoPresupuestario.objects.get(instituto=alfa, gestion=2026).monto_bs == Decimal(
            "150000.00"
        )
        assert Carrera.objects.filter(instituto=alfa).count() == 2
        assert DerechoPropietario.objects.get(instituto=alfa).apto_para_inversion
        # Por defecto no se guardan teléfonos (minimización).
        assert AutoridadInstituto.objects.get(instituto=alfa).telefono == ""
        assert ObservacionDato.objects.filter(texto__contains="Folio real").count() == 2
        registro = Bitacora.objects.get(accion="institutos_importados")
        assert set(registro.despues["huellas_sha256"]) == {"datos", "ficha"}
        # Los datos personales no van a la bitácora de la importación ni a los proyectos.
        assert "70000001" not in str(registro.despues)
        assert not Bitacora.objects.filter(despues__icontains="70000001").exists()

    def test_reimportar_no_duplica(self, planillas, unidad):
        lectura = importador.leer(*planillas)
        services.importar(lectura=lectura, unidad=unidad)
        conteos = (
            Instituto.objects.count(),
            Proyecto.objects.count(),
            ObservacionDato.objects.count(),
        )
        informe = services.importar(lectura=importador.leer(*planillas), unidad=unidad)
        assert informe.institutos_actualizados == 3 and informe.institutos_nuevos == 0
        assert conteos == (
            Instituto.objects.count(),
            Proyecto.objects.count(),
            ObservacionDato.objects.count(),
        )

    def test_cambio_de_rector_conserva_historial(self, tmp_path, planillas, unidad):
        services.importar(lectura=importador.leer(*planillas), unidad=unidad)
        from .planillas_sinteticas import FICHAS

        fichas = dict(FICHAS)
        fichas[1] = fichas[1].replace("Persona Ficticia Uno", "Persona Ficticia Nueva")
        nueva = crear_ficha(tmp_path / "ficha2.xlsx", fichas)
        services.importar(lectura=importador.leer(planillas[0], nueva), unidad=unidad)
        autoridades = AutoridadInstituto.objects.filter(instituto__numero=1)
        assert {(a.nombre, a.vigente) for a in autoridades} == {
            ("Persona Ficticia Uno", False),
            ("Persona Ficticia Nueva", True),
        }


class TestComando:
    def test_simular_por_comando(self, planillas, unidad, capsys):
        call_command(
            "importar_institutos", "--datos", str(planillas[0]), "--ficha", str(planillas[1]),
            "--unidad", unidad.sigla, "--simular",
        )  # fmt: skip
        salida = capsys.readouterr().out
        assert "SIMULACIÓN" in salida and "Folio real" in salida
        assert not Instituto.objects.exists()

    def test_unidad_inexistente(self, planillas):
        with pytest.raises(CommandError, match="No existe la unidad"):
            call_command(
                "importar_institutos", "--datos", str(planillas[0]), "--ficha", str(planillas[1]),
                "--unidad", "NOEXISTE",
            )  # fmt: skip

    def test_archivo_no_valido_por_comando(self, tmp_path, planillas, unidad):
        falso = tmp_path / "falso.xlsx"
        falso.write_text("hola")
        with pytest.raises(CommandError, match="no es un libro"):
            call_command(
                "importar_institutos", "--datos", str(falso), "--ficha", str(planillas[1]),
                "--unidad", unidad.sigla,
            )  # fmt: skip

    def test_informe_y_observaciones_extra(self, tmp_path, planillas, unidad):
        extra = tmp_path / "extra.csv"
        extra.write_text("1;Verificar dirección con la Dirección\nnumero;texto\n", encoding="utf-8")
        informe = tmp_path / "informe.csv"
        call_command(
            "importar_institutos", "--datos", str(planillas[0]), "--ficha", str(planillas[1]),
            "--unidad", unidad.sigla, "--observaciones-extra", str(extra),
            "--informe", str(informe),
        )  # fmt: skip
        assert ObservacionDato.objects.filter(texto="Verificar dirección con la Dirección").exists()
        assert "Verificar dirección" in informe.read_text(encoding="utf-8")


def test_telefonos_solo_si_se_habilita(planillas, unidad, settings):
    settings.INSTITUTOS_CARGAR_TELEFONOS = True
    services.importar(lectura=importador.leer(*planillas), unidad=unidad)
    assert AutoridadInstituto.objects.get(instituto__numero=1).telefono == "70000001"
