"""Lectura de las planillas de institutos (formato v1). No toca la base de datos.

Formato esperado:
- **Planilla de datos**: hoja con una fila de encabezados que contiene «NOMBRE» y
  «MUNICIPIO»; columnas A-M: N°, provincia, municipio, región, nombre, ubicación,
  situación, población estudiantil (el encabezado indica mes/año), infraestructura,
  refacciones y tres columnas de equipamiento por gestión.
- **Ficha técnica**: columna C = N°, columna D = texto con líneas «* Etiqueta: valor».

Seguridad: solo `.xlsx` (sin macros), tamaño y descompresión limitados, lectura en
modo solo valores (sin fórmulas), XML con defusedxml (openpyxl lo usa si está instalado).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.conf import settings

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
    "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}  # fmt: skip
MAX_FILAS = 2000
AVISO_GESTIONES = (
    "Las gestiones de equipamiento están escritas en una fila de datos y no en el encabezado."
)
MAX_DESCOMPRIMIDO = 200 * 1024 * 1024  # contra archivos "bomba" de compresión
MAX_ENTRADAS_ZIP = 500


class ArchivoNoValido(Exception):
    """El archivo no es una planilla aceptable."""


@dataclass
class ProyectoLeido:
    tipo: str
    nombre: str
    presupuesto_bs: Decimal | None
    estado_texto: str
    estado: str
    gestion_inicio: int | None
    gestion_fin: int | None


@dataclass
class InstitutoLeido:
    numero: int
    nombre: str
    provincia: str = ""
    municipio: str = ""
    region: str = ""
    direccion: str = ""
    situacion: str = ""
    es_subsede: bool = False
    estudiantes: int | None = None
    proyectos: list[ProyectoLeido] = field(default_factory=list)
    # De la ficha técnica
    en_ficha: bool = False
    rector: str = ""
    telefono: str = ""
    resolucion: str = ""
    resolucion_anio: int | None = None
    dependencia_texto: str = ""
    techo_bs: Decimal | None = None
    carreras: list[str] = field(default_factory=list)
    derecho_texto: str = ""
    folio_real: str = ""
    derecho_estado: str = "sin_dato"


@dataclass
class Lectura:
    institutos: dict[int, InstitutoLeido]
    observaciones: list[tuple[int | None, str]]
    matricula_anio: int | None
    matricula_mes: int | None
    techo_gestion: int | None
    huellas: dict[str, str]


# --- Utilidades -----------------------------------------------------------------------


def limpio(valor) -> str:
    if valor is None:
        return ""
    return re.sub(r"[ \t]+", " ", str(valor).replace("\r", "")).strip()


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.upper())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def monto(texto: str) -> Decimal | None:
    """'15.054.108,05 Bs' -> 15054108.05; '160,000,00' -> 160000.00; None si no hay cifra."""
    coincidencia = re.search(r"(\d[\d.,]*\d|\d)", texto or "")
    if not coincidencia:
        return None
    cifra = coincidencia.group(1)
    partes = re.match(r"^(.*)[.,](\d{2})$", cifra)  # último separador + 2 dígitos = decimales
    entero, decimales = (partes.group(1), partes.group(2)) if partes else (cifra, "00")
    entero = re.sub(r"[.,]", "", entero) or "0"
    return Decimal(f"{entero}.{decimales}")


def estado_de(texto: str) -> str:
    t = texto.lower()
    if "paraliz" in t:
        return "paralizada"
    if "ejecuci" in t or "proceso" in t:
        return "en_ejecucion"
    if "sin cierre" in t:
        return "concluida_sin_cierre_financiero"
    if "acta de entrega provisional" in t:
        return "recepcion_provisional"
    if "conclu" in t:
        return "concluida"
    return "sin_dato"


def huella(ruta: Path) -> str:
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(65536), b""):
            sha.update(bloque)
    return sha.hexdigest()


def validar_archivo(ruta: Path) -> None:
    """Rechaza lo que no sea un .xlsx razonable antes de abrirlo con openpyxl."""
    if ruta.suffix.lower() != ".xlsx":
        raise ArchivoNoValido(f"{ruta.name}: solo se aceptan archivos .xlsx (sin macros).")
    if not ruta.is_file():
        raise ArchivoNoValido(f"{ruta.name}: no existe.")
    max_bytes = settings.IMPORTACION_MAX_MB * 1024 * 1024
    if ruta.stat().st_size > max_bytes:
        raise ArchivoNoValido(f"{ruta.name}: supera {settings.IMPORTACION_MAX_MB} MB.")
    with ruta.open("rb") as archivo:
        if archivo.read(4) != b"PK\x03\x04":
            raise ArchivoNoValido(f"{ruta.name}: el contenido no es un libro de Excel válido.")
    try:
        with zipfile.ZipFile(ruta) as contenedor:
            entradas = contenedor.infolist()
            if len(entradas) > MAX_ENTRADAS_ZIP:
                raise ArchivoNoValido(f"{ruta.name}: estructura interna anómala.")
            if sum(e.file_size for e in entradas) > MAX_DESCOMPRIMIDO:
                raise ArchivoNoValido(f"{ruta.name}: contenido descomprimido demasiado grande.")
            if any(e.filename.lower().endswith("vbaproject.bin") for e in entradas):
                raise ArchivoNoValido(f"{ruta.name}: contiene macros.")
    except zipfile.BadZipFile as error:
        raise ArchivoNoValido(f"{ruta.name}: archivo dañado.") from error


def _abrir(ruta: Path):
    validar_archivo(ruta)
    return openpyxl.load_workbook(ruta, read_only=True, data_only=True, keep_links=False)


# --- Planilla de datos ----------------------------------------------------------------


def _proyectos(celda, tipo: str, numero: int, observaciones) -> list[ProyectoLeido]:
    texto = limpio(celda)
    if not texto:
        return []
    leidos: list[dict] = []
    for linea in (x.strip() for x in texto.split("\n")):
        if not linea:
            continue
        if linea.upper().startswith("PRESUPUESTO"):
            if leidos:
                leidos[-1]["presupuesto_bs"] = monto(linea)
        elif linea.startswith("*"):
            if leidos:
                leidos[-1]["estados"].append(linea.lstrip("* ").strip())
        else:
            gestion = re.search(r"\((\d{4})(?:-(\d{4}))?\)", linea)
            inicio = int(gestion.group(1)) if gestion else None
            fin = int(gestion.group(2)) if gestion and gestion.group(2) else inicio
            leidos.append(
                {
                    "nombre": linea[:300],
                    "presupuesto_bs": None,
                    "estados": [],
                    "ini": inicio,
                    "fin": fin,
                }
            )
    resultado = []
    for p in leidos:
        estado_texto = " · ".join(p["estados"])
        if p["presupuesto_bs"] is None:
            observaciones.append((numero, f"Proyecto sin presupuesto legible: {p['nombre'][:80]}"))
        resultado.append(
            ProyectoLeido(
                tipo=tipo,
                nombre=p["nombre"],
                presupuesto_bs=p["presupuesto_bs"],
                estado_texto=estado_texto,
                estado=estado_de(estado_texto),
                gestion_inicio=p["ini"],
                gestion_fin=p["fin"],
            )
        )
    return resultado


def _es_anio(valor) -> bool:
    return bool(re.fullmatch(r"(19|20)\d{2}", limpio(valor)))


def leer_datos(
    ruta: Path, observaciones
) -> tuple[dict[int, InstitutoLeido], int | None, int | None]:
    libro = _abrir(ruta)
    hoja = libro.worksheets[0]
    filas = list(hoja.iter_rows(max_row=MAX_FILAS + 20, max_col=13, values_only=True))
    libro.close()
    if len(filas) > MAX_FILAS + 10:
        raise ArchivoNoValido(f"{ruta.name}: más de {MAX_FILAS} filas.")

    encabezado_idx = next(
        (
            i for i, fila in enumerate(filas[:30])
            if {"NOMBRE", "MUNICIPIO"} <= {normalizar(limpio(c)) for c in fila}
        ),
        None,
    )  # fmt: skip
    if encabezado_idx is None:
        raise ArchivoNoValido(
            f"{ruta.name}: no se encontró la fila de encabezados (NOMBRE, MUNICIPIO)."
        )
    encabezado = [normalizar(limpio(c)) for c in filas[encabezado_idx]]

    # Mes y año de la matrícula desde el encabezado (ej. «POBLACIÓN ESTUDIANTIL JULIO/2026»).
    matricula_anio = matricula_mes = None
    texto_matricula = encabezado[7] if len(encabezado) > 7 else ""
    if (m := re.search(r"(19|20)\d{2}", texto_matricula)) is not None:
        matricula_anio = int(m.group())
    matricula_mes = next((n for nombre, n in MESES.items() if nombre in texto_matricula), None)

    datos = [f for f in filas[encabezado_idx + 1 :] if isinstance(f[0], (int, float))]
    # Gestiones de equipamiento: en el encabezado o, si no, en la primera fila de datos.
    gestiones = [None, None, None]
    for fuente in [
        filas[encabezado_idx],
        filas[encabezado_idx + 1] if len(filas) > encabezado_idx + 1 else (),
    ]:
        valores = list(fuente[10:13]) if len(fuente) >= 13 else []
        if valores and all(_es_anio(v) for v in valores):
            gestiones = [int(limpio(v)) for v in valores]
            if fuente is not filas[encabezado_idx]:
                numero_fila = int(fuente[0]) if isinstance(fuente[0], (int, float)) else None
                observaciones.append((numero_fila, AVISO_GESTIONES))
            break

    institutos: dict[int, InstitutoLeido] = {}
    for fila in datos:
        fila = list(fila) + [None] * (13 - len(fila))
        numero = int(fila[0])
        if numero in institutos:
            observaciones.append(
                (numero, "N° repetido en la planilla de datos; se usó la primera fila.")
            )
            continue
        nombre = limpio(fila[4]).strip(" /")[:250]
        estudiantes = re.search(r"\d+", limpio(fila[7]))
        inst = InstitutoLeido(
            numero=numero,
            nombre=nombre,
            provincia=limpio(fila[1]).replace("PROVINCIA ", "").title()[:80],
            municipio=limpio(fila[2])[:80],
            region=limpio(fila[3])[:60],
            direccion=limpio(fila[5]).strip(" /")[:300],
            situacion=limpio(fila[6])[:200],
            es_subsede=bool(re.search(r"SUB ?SEDE", nombre, re.I)),
            estudiantes=int(estudiantes.group()) if estudiantes else None,
        )
        inst.proyectos += _proyectos(fila[8], "construccion", numero, observaciones)
        inst.proyectos += _proyectos(fila[9], "refaccion", numero, observaciones)
        for indice, gestion in enumerate(gestiones):
            valor = limpio(fila[10 + indice])
            if not valor or _es_anio(valor) or gestion is None:
                continue
            inst.proyectos.append(
                ProyectoLeido(
                    tipo="equipamiento",
                    nombre=f"Equipamiento {gestion}",
                    presupuesto_bs=monto(valor),
                    estado_texto=valor.replace("\n", " ")[:500],
                    estado="programado" if "POR EJECUTAR" in valor.upper() else "concluida",
                    gestion_inicio=gestion,
                    gestion_fin=gestion,
                )
            )
        institutos[numero] = inst
    return institutos, matricula_anio, matricula_mes


# --- Ficha técnica --------------------------------------------------------------------


def _patrones_titular() -> list[str]:
    """Textos que indican que el inmueble está a nombre de la entidad (configurables)."""
    return [normalizar(p) for p in settings.INSTITUTOS_TITULAR_PATRONES if p.strip()]


def _campo(texto: str, etiqueta: str) -> str:
    coincidencia = re.search(rf"\*\s*{etiqueta}[^:\n]*:\s*(.*)", texto, flags=re.I)
    return coincidencia.group(1).strip() if coincidencia else ""


def leer_ficha(ruta: Path, institutos: dict[int, InstitutoLeido], observaciones) -> int | None:
    libro = _abrir(ruta)
    hoja = libro.worksheets[0]
    techo_gestion = None
    for fila in hoja.iter_rows(max_row=MAX_FILAS + 20, max_col=4, values_only=True):
        fila = list(fila) + [None] * (4 - len(fila))
        if not isinstance(fila[2], (int, float)):
            continue
        numero = int(fila[2])
        texto = limpio(fila[3])[:20000]
        inst = institutos.get(numero)
        if inst is None:
            observaciones.append(
                (
                    None,
                    f"El N° {numero} aparece en la ficha técnica pero no en la planilla de datos.",
                )
            )
            continue
        inst.en_ficha = True
        nombre_ficha = texto.split("\n")[0].strip()
        if normalizar(nombre_ficha)[:25] != normalizar(inst.nombre)[:25]:
            observaciones.append(
                (
                    numero,
                    f"Nombre distinto entre archivos: «{inst.nombre[:60]}» / "
                    f"«{nombre_ficha[:60]}».",
                )
            )
        inst.rector = _campo(texto, "Rector")[:150]
        inst.telefono = _campo(texto, "Celular")[:40]
        inst.resolucion = _campo(texto, "Resoluci")[:300]
        if (m := re.search(r"(\d{1,4})\s*/\s*(\d{2,4})\b", inst.resolucion)) is not None:
            anio = int(m.group(2))
            inst.resolucion_anio = anio + 2000 if anio < 100 else anio
        inst.dependencia_texto = _campo(texto, "Dependencia")[:150]
        etiqueta_techo = re.search(r"\*\s*Techo[^:\n]*", texto, flags=re.I)
        if etiqueta_techo and (g := re.search(r"(19|20)\d{2}", etiqueta_techo.group())):
            techo_gestion = techo_gestion or int(g.group())
        inst.techo_bs = monto(_campo(texto, "Techo"))
        if not inst.techo_bs:
            observaciones.append((numero, "Techo presupuestario sin monto legible."))
        estudiantes_ficha = re.search(r"\d+", _campo(texto, "Cantidad de Estudiantes"))
        if (
            estudiantes_ficha
            and inst.estudiantes
            and int(estudiantes_ficha.group()) != inst.estudiantes
        ):
            observaciones.append(
                (
                    numero,
                    "Estudiantes distintos entre archivos: "
                    f"{inst.estudiantes} / {estudiantes_ficha.group()}.",
                )
            )
        bloque = re.search(r"Oferta Acad[eé]mica:?(.*?)(\*\s*Derecho|$)", texto, flags=re.S | re.I)
        inst.carreras = [
            linea.strip(" -").strip()[:200]
            for linea in (bloque.group(1) if bloque else "").split("\n")
            if linea.strip().startswith("-") and linea.strip(" -").strip()
        ][:100]
        inst.derecho_texto = _campo(texto, "Derecho Propietario")[:2000]
        folio = re.search(r"Folio Real\s*([\d.]+\d)", inst.derecho_texto, flags=re.I)
        inst.folio_real = folio.group(1)[:40] if folio else ""
        d = inst.derecho_texto.lower()
        if "proceso" in d or "trámite" in d or "tramite" in d:
            inst.derecho_estado = (
                "en_proceso_con_folio" if inst.folio_real else "en_proceso_sin_antecedentes"
            )
        elif any(patron in normalizar(d) for patron in _patrones_titular()):
            inst.derecho_estado = "a_nombre_entidad"
        elif not d:
            inst.derecho_estado = "sin_dato"
        else:
            inst.derecho_estado = "otro"
    libro.close()
    return techo_gestion


def leer(
    datos: Path, ficha: Path, observaciones_extra: list[tuple[int | None, str]] | None = None
) -> Lectura:
    observaciones: list[tuple[int | None, str]] = []
    institutos, matricula_anio, matricula_mes = leer_datos(datos, observaciones)
    techo_gestion = leer_ficha(ficha, institutos, observaciones)

    folios: dict[str, list[int]] = {}
    for inst in institutos.values():
        if not inst.en_ficha:
            observaciones.append((inst.numero, "No aparece en la ficha técnica."))
        if inst.derecho_estado == "sin_dato" and inst.en_ficha:
            observaciones.append((inst.numero, "Derecho propietario sin dato."))
        if inst.folio_real:
            folios.setdefault(inst.folio_real, []).append(inst.numero)
    for folio, numeros in folios.items():
        if len(numeros) > 1:
            for numero in numeros:
                otros = ", ".join(str(n) for n in numeros)
                observaciones.append(
                    (numero, f"Folio real {folio} repetido en los institutos N° {otros}.")
                )
    observaciones.extend(observaciones_extra or [])
    return Lectura(
        institutos=institutos,
        observaciones=observaciones,
        matricula_anio=matricula_anio,
        matricula_mes=matricula_mes,
        techo_gestion=techo_gestion,
        huellas={"datos": huella(datos), "ficha": huella(ficha)},
    )
