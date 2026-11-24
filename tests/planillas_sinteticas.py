"""Genera planillas FICTICIAS con la estructura de las reales (formato v1)."""

from pathlib import Path

import openpyxl

ENCABEZADO = [
    "Nª",
    "PROVINCIA",
    "MUNICIPIO",
    "REGIÓN",
    "NOMBRE DEL INSTITUTO TÉCNICO TECNOLÓGICO",
    "UBICACIÓN ",
    "SITUACIÓN EN FUNCIONAMIENTO ",
    "POBLACIÓN ESTUDIANTIL       JULIO/ 2026",
    "INFRAESTRUCTURA (2021-2025)",
    "REFACCIONES (2021-2025)",
    "EQUIPAMIENTO",
    None,
    None,
]

FILAS = [
    [
        1, "PROVINCIA UNO", "Municipio A", "Altiplano", "INSTITUTO TECNOLÓGICO ALFA", "Zona Centro",
        "En funcionamiento", "350",
        "CONSTRUCCIÓN BLOQUE A (2022-2024)\nPRESUPUESTO: 1.500.000,50 Bs\n* En ejecución\n"
        "AMPLIACIÓN TALLER (2025)\nPRESUPUESTO 200.000,00\n* Paralizada por resolución",
        "", "2024", "2025", "2026",
    ],
    [
        2, "PROVINCIA UNO", "Municipio A", "Altiplano", "INSTITUTO TÉCNICO BETA SUB SEDE",
        "Calle 2", "En funcionamiento", "120", "",
        "REFACCIÓN DE AULAS (2023)\nPRESUPUESTO: 80,000.00\n* Concluida sin cierre financiero",
        "350.000,00 Bs", "", "POR EJECUTAR 90.000,00",
    ],
    [
        3, "PROVINCIA DOS", "Municipio C", "Valles", "INSTITUTO GAMMA", "Av. 3",
        "En funcionamiento", "80", "OBRA SIN MONTO (2021)\n* Concluida", "", None, None, None,
    ],
]  # fmt: skip

FICHAS = {
    1: "INSTITUTO TECNOLÓGICO ALFA\n* Rector: Persona Ficticia Uno\n* Celular: 70000001\n"
    "* Resolución Ministerial: 123/2015\n* Cantidad de Estudiantes: 350\n* Dependencia: Fiscal\n"
    "* Techo Presupuestario 2026: 150.000,00 Bs\n* Oferta Académica:\n- Mecánica Automotriz\n"
    "- Contaduría\n"
    "* Derecho Propietario: A nombre del Gobierno Autónomo, Folio Real 2.01.0.99.000001",
    2: "INSTITUTO TECNICO BETA SUB SEDE\n* Rector: Persona Ficticia Dos\n* Celular: 70000002\n"
    "* Resolución Ministerial: 45/09\n* Cantidad de Estudiantes: 130\n* Dependencia: De convenio\n"
    "* Techo Presupuestario 2026: sin dato\n* Oferta Académica:\n- Agropecuaria\n"
    "* Derecho Propietario: En proceso de saneamiento, Folio Real 2.01.0.99.000001",
    3: "OTRO NOMBRE DISTINTO\n* Rector: Persona Ficticia Tres\n* Dependencia: Fiscal\n"
    "* Techo Presupuestario 2026: 50.000,00\n* Oferta Académica:\n- Gastronomía\n"
    "* Derecho Propietario: En trámite sin antecedentes",
    99: "INSTITUTO QUE NO ESTÁ EN DATOS\n* Rector: Nadie",
}


def crear_datos(ruta: Path, filas=None) -> Path:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Hoja1"
    hoja.append(["DIRECCIÓN DE EJEMPLO"])
    hoja.append(["INSTITUTOS TÉCNICOS TECNOLÓGICOS (DATOS FICTICIOS)"])
    hoja.append([])
    hoja.append(ENCABEZADO)
    for fila in FILAS if filas is None else filas:
        hoja.append(fila)
    libro.save(ruta)
    return ruta


def crear_ficha(ruta: Path, fichas=None) -> Path:
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["FICHA TÉCNICA (DATOS FICTICIOS)"])
    hoja.append([])
    hoja.append([])
    hoja.append([None, None, "N°", "DETALLE"])
    for numero, texto in (FICHAS if fichas is None else fichas).items():
        hoja.append([None, None, numero, texto])
    libro.save(ruta)
    return ruta
