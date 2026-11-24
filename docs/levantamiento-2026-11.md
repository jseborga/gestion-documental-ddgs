# DDGS: análisis del levantamiento y ajustes al MVP

Versión 1.0 · 24/11/2026 · Fuentes: 10 cuestionarios por cargo y 7 encuestas anónimas (respondidos el 18/11/2026), Hoja de Ruta N° 814/2025 (modelo), MOF 2027 de la Secretaría Departamental de Gestión Social (borrador para validación, recibido el 22/10/2026) y Decreto Departamental N° 100 de 03/08/2017 (transcripción en Word).

Los nombres de quienes respondieron no se registran aquí; se citan por cargo.

## 1. Conclusiones principales

1. **El problema central es la trazabilidad, no el número de CITE.** 5 de 7 encuestados dedican más de 5 horas por semana a buscar documentos o preguntar por un trámite; 4 de 7 dicen que *siempre* desconocen quién tiene un trámite, y 6 de 7 tuvieron al menos un plazo vencido este año. En cambio, obtener un CITE es "muy fácil" para 5 de 7 (lo sacan desde el celular en el registro de Google Drive). El dolor del CITE no es conseguirlo, sino los **duplicados y reservas en blanco** que eso genera.
2. **La hoja de ruta no es de la Dirección.** La genera Ventanilla Única de la Gobernación y se sigue en el sistema *SMAIL*. La DDGS no numera hojas de ruta: registra la entrada en un **cuaderno de actas** y el profesional firma el cuaderno al recibir. El sistema debe **guardar el número de HR de Ventanilla Única como referencia externa** y reemplazar el cuaderno de actas, no crear una segunda numeración de HR.
3. **Los plazos se pierden antes de llegar.** El Director señala que los plazos corren desde el ingreso a la Gobernación y no desde que el trámite llega a la Dirección. El sistema debe registrar las dos fechas y calcular la **demora previa** para documentarlo.
4. **Todo pasa por el Director** (respuesta textual: "absolutamente todos"). La bandeja de la Dirección es el cuello de botella natural; el MVP debe hacer esa revisión rápida (cola única ordenada por prioridad y plazo), no intentar saltarla.
5. **Falta de formatos estandarizados** es la causa más citada de observaciones en contrataciones e informes técnicos ("cada técnico tiene un criterio"). Plantillas y listas de requisitos por trámite valen tanto como el flujo.
6. **Los fiscales de obra piden alertas de garantías** (boletas y pólizas) con aviso a 15 y 5 días, y seguimiento de planillas detenidas. Hoy se controlan en Excel, teléfono y WhatsApp.

## 2. Ajustes decididos para el MVP

| # | Ajuste | Origen | Cambio en el diseño |
| --- | --- | --- | --- |
| A1 | Registro de entrada sin numerar HR propia | Secretaría, Hoja de Ruta 814 | `Expediente` gana `hr_ventanilla` (texto, opcional), `fecha_ingreso_gobernacion`, `fecha_recepcion_unidad`, `hora_recepcion`, `fojas`, `soporte` (original, copia, fax, otro), `prioridad` (urgente, prioritario, rutinario), `cite_origen`. Indicador "demora previa" = recepción − ingreso. |
| A2 | Acuse digital en lugar del cuaderno de actas | Secretaría | Al derivar, el destinatario confirma recepción con un clic; queda fecha y hora en bitácora. Constancia imprimible para quien la pida. |
| A3 | Derivación con proveído, acción y varios destinos | Hoja de Ruta 814 (paso 3: cuatro destinos a la vez) | `Derivacion` gana `accion` (para conocimiento, informar, acuse de recibo, archivar, atender/elaborar respuesta) y `fojas`. Una derivación puede tener varios destinos paralelos, cada uno con su acuse y su plazo. |
| A4 | Firmas múltiples y visto bueno fuera de la Dirección | Director, Secretaría | `Documento` gana lista ordenada de firmantes (elaborador, Director, Secretaria Departamental según tipo). El visto bueno de la Secretaría Departamental se registra como paso externo con fechas de salida y retorno, porque el piloto es solo de la Dirección. |
| A5 | CITE solo al firmar; reservas desactivadas por defecto | Director (sin reservas), Secretaría (propone 24 h) | `CITE_RESERVA_HORAS=0` por defecto. Si la Dirección la habilita, máximo 24 h y anulación automática con constancia. Prohibido el sufijo "-A": el importador marca los históricos "455-A" como duplicados a revisar. El CITE debe poder verse desde el celular. |
| A6 | Documentos relacionados | Secretaría ("la nota venía con un informe") | Relación `DocumentoRelacionado` (remite, adjunta, responde a), cada uno con su CITE. El archivo los agrupa. |
| A7 | Circulares con un solo CITE | Secretaría, responsable de equipamiento (CODAN) | En comunicados, instructivos y circulares: **un CITE** con lista de destinatarios. En notas personalizadas: un CITE por destinatario. Se configura por tipo de documento (corrige SPEC §2.1, que decía un CITE por destinatario en todo envío masivo). |
| A8 | Seguimiento de respuestas a circulares | Secretaría (picos de correspondencia tras instructivos), CODAN (30 invitaciones a la Expoferia) | Tablero "quién respondió" por circular; las respuestas que llegan se vinculan al expediente de la circular. La difusión por WhatsApp queda como marca manual en el MVP; correo electrónico desde el sistema como opción. |
| A9 | Escaneo obligatorio al despachar | Secretaría (copias que no llegan al archivo) | No se puede cerrar el despacho sin el PDF del documento firmado. |
| A10 | Documentos reservados con lista de acceso | Director (llamadas de atención), Legal (CPE, Ley 2341, DS 28168) | Clasificación `reservado` con lista explícita de quién puede verlo (destinatario, firmante, Director). Ni el buscador ni el tablero muestran su contenido. |
| A11 | Informe de los lunes | Director | Tablero semanal: estado de trámites de toda la Dirección, trámites atendidos por funcionario en la semana, vencidos y por vencer, demora previa. "Metas alcanzadas" queda pendiente: no hay metas definidas en lo recibido. |
| A12 | Suplencia designada por la Secretaría | Director | `OcupacionCargo` interino o suplente con referencia al memorándum de designación. |
| A13 | Plantillas y listas de requisitos por trámite | Coordinadores de educación y de proyectos | Catálogo `TipoTramite` con plantilla, requisitos (lista de verificación) y plazo. Primer contenido: inicio de proceso de contratación (ver §4) y los trámites del Decreto Departamental 100 (ver `docs/modulo-institutos.md` §10). |
| A14 | Registro de garantías con alertas (adelanto de la fase 3) | Tres fiscales de obra | Entidad `Garantia` (proyecto, tipo: cumplimiento, anticipo, correcta inversión; entidad emisora; número; monto; vencimiento; estado de renovación). Alertas por correo a 15 y 5 días y al vencer sin renovación. Planillas, órdenes de cambio y avance siguen en la fase 3. |
| A15 | Estructura programática en el expediente | Coordinadora de proyectos | Campos opcionales DA, UE, programa, proyecto, actividad, fuente, partida y operación POA. Se llenan a mano: no hay API de SIGEP conocida. |
| A16 | Respaldos solo en Bolivia hasta autorización | Respuestas contradictorias (Legal: viable; auxiliar: "no, por soberanía tecnológica") | `BACKUP_DESTINOS` por defecto: local + segundo sitio en Bolivia (SFTP). Los destinos en nubes extranjeras quedan desactivados hasta autorización escrita de la Unidad de Sistemas y del Responsable de Seguridad de la Información. |
| A17 | Plazos de conservación configurables | Auxiliar administrativo (práctica); Director (no existe política escrita) | Valores iniciales: 2 años en la Dirección, 10 en archivo central, permanente para control y auditoría. Son la práctica declarada, no una norma: requieren aprobación formal. |
| A18 | Uso en equipos lentos y en celular | Fiscal de obra (equipos lentos), encuesta (acceso desde campo) | Páginas livianas (HTMX, sin SPA); prueba de aceptación en un equipo real de la Dirección y en celular. |

## 3. Estructura orgánica (MOF 2027, borrador)

- **Secretaría Departamental de Gestión Social (SDGS)**, depende de la Secretaría Ejecutiva Departamental. Autoridad lineal sobre la **Dirección de Desarrollo y Gestión Social (DDGS)**, la **Dirección de Política Social (DPS)** y la **Dirección del Comité Departamental de las Personas con Discapacidad (CODEPEDIS)**; autoridad funcional sobre el **SEDEGES** (desconcentrado).
- La DDGS **no tiene unidades dependientes**: el sistema se organiza por cargos, no por subunidades.
- Las funciones de la DDGS cubren institutos técnicos tecnológicos (infraestructura, equipamiento, mantenimiento, inspecciones, criterio técnico para nuevos institutos y carreras), seguridad alimentaria y nutricional, y unidades productivas en institutos.
- La Hoja de Ruta 814/2025 se derivó a la vez a varias direcciones de la Secretaría: la **segunda ola natural del piloto es la SDGS con sus tres direcciones**, no otra Secretaría.
- Siembra de datos: estas cuatro unidades y la Secretaría Ejecutiva como catálogo inicial (sin personas reales en el repositorio).

## 4. Inicio de proceso de contratación: lista preliminar

Unión de lo declarado por dos coordinadores. **Debe validarla la Unidad de Contrataciones** antes de usarla como requisito obligatorio:

1. Informe de necesidad o justificación.
2. Especificaciones técnicas.
3. Análisis financiero o precio referencial (cuadro comparativo, reporte del Mercado Virtual, búsqueda en Compro Hecho en Bolivia).
4. Certificación POA e inscripción en el PAC.
5. Certificación presupuestaria.
6. Formulario de material de suministros (cuando corresponde).
7. Informe y nota de solicitud de inicio del proceso.
8. Documento Base de Contratación, resolución o autorización de inicio y publicación en SICOES.
9. Notas de designación de la comisión de calificación e informe de la comisión.

## 5. Calidad de la información recibida

Esto no descalifica el trabajo de quienes respondieron, pero limita cuánto se puede confiar en cada dato:

1. **Personal muy nuevo.** Quienes respondieron llevan entre 9 días y 3 meses en el cargo. Las respuestas describen semanas de experiencia, no la memoria institucional; dos personas responden de oídas ("aún no lo vi", "no tengo conocimiento").
2. **El cuestionario de Sistemas y Seguridad lo respondió un auxiliar administrativo con 14 días en el cargo**, no la Unidad de Sistemas ni el Responsable de Seguridad de la Información. Sus respuestas sobre alojamiento ("en la parte posterior de las oficinas"), respaldos ("encargada de secretaría y un cuaderno") y API ("no sé") no sirven para decidir infraestructura. **Hay que repetir ese cuestionario con la Unidad de Sistemas.**
3. **Respuestas genéricas.** Dos respuestas (la del fiscal de arquitectura y la de asesoría legal sobre nubes) son extensas pero sin un solo caso concreto (ningún CITE, fecha ni proyecto) y usan expresiones ajenas al contexto ("tu organización", "empresas privadas"). Parecen redactadas con ayuda de una herramienta. Se usan como orientación, no como evidencia.
4. **Contradicciones a resolver:** quién aprueba una orden de cambio (un fiscal: "aprueba el fiscal"; otro: la supervisión evalúa y la fiscalización aprueba; un tercero, genérico); si se puede respaldar en una nube extranjera (sí según Legal, no según el auxiliar); si debe haber reservas de CITE (no según el Director, 24 h según la Secretaría); el valor del archivo digital (Legal: la firma digital tiene plena validez; auxiliar: "no tiene el mismo valor").
5. **Las encuestas "anónimas" no lo son**: hay una por rol y la función identifica a la persona. Además, las siete parecen copias del mismo archivo editado (patrones idénticos, casillas que quedaron marcadas de la primera). Sirven como línea base indicativa, no estadística: son 7 de unas 20 personas.
6. **Volumen declarado frente a registrado.** Las encuestas suman unos 100 documentos elaborados por semana; el registro de CITE 2026 tiene 1.219 documentos en el año, del orden de 25 a 30 por semana. O muchos documentos no pasan por el registro (borradores, informes internos), o el número está sobrestimado. Conviene medirlo en las dos primeras semanas del piloto.
7. **El Decreto Departamental 100 no es un reglamento de correspondencia.** El Director lo cita como tal y como tabla de plazos, pero regula la dotación y el financiamiento a institutos técnicos tecnológicos. Sus plazos aplican a esos trámites; el reglamento de correspondencia y archivo de la Gobernación sigue sin aparecer.

## 6. Observaciones a los documentos normativos

**Decreto Departamental 100 (2017):**
- El artículo primero dice que el reglamento tiene 36 artículos, una disposición transitoria y cuatro finales; el texto recibido tiene 37 artículos y ninguna sección titulada "disposición transitoria" (el artículo 24 trata medidas transitorias).
- Servicios básicos se define distinto en el artículo 6.f (incluye postal y telecomunicaciones) y en el 17 (solo agua, alcantarillado, electricidad y gas).
- Los considerandos atribuyen el mismo texto a los artículos 77.I y 90.I de la Constitución.
- Usa nombres de unidades de 2017 ("Dirección de Desarrollo Social", "Secretaría Departamental de Desarrollo Social y Comunitario"). Equivalencia asumida, **a confirmar**: hoy DDGS y SDGS.
- Es una transcripción en Word. No encontré en línea la publicación oficial ni sus modificaciones: **hay que confirmar con Asuntos Jurídicos que sigue vigente y sin cambios.**
- La Disposición Final Tercera encarga a la Dirección "generar una base de datos de los Institutos… con el objeto de contar con mecanismos de control": es la **base normativa del módulo Institutos**.

**MOF 2027 (borrador):**
- La Dirección de Política Social (función k) y el SEDEGES (función q) todavía citan a la "Secretaría Departamental de Desarrollo Social y Comunitario".
- Las funciones de la DDGS no mencionan la base de datos de institutos que exige el Decreto 100 ni la gestión documental de la Dirección. El plazo de validación (27/10/2026) ya venció; queda para la próxima revisión.

## 7. Pendientes que bloquean decisiones

| Pendiente | A quién | Bloquea |
| --- | --- | --- |
| Cuestionario de Sistemas y Seguridad respondido por la Unidad de Sistemas y el Responsable de Seguridad | Unidad de Sistemas | Alojamiento, inicio de sesión (el auxiliar dice que existe un directorio de usuarios, sin decir cuál), respaldos, Docker |
| Qué es SMAIL, quién lo administra y si exporta datos o tiene API | Ventanilla Única / Sistemas | Importar el número y estado de la HR en vez de tipearlos |
| Plantillas vigentes de nota, informe, memorándum, instructivo y comunicado | Dirección (ofrecidas) | A13 |
| Lista de proyectos 2026 con código e instituto; lista de instituciones | Dirección (ofrecidas) | Catálogos iniciales |
| PISI de la Gobernación | Dirección (ofrecido) | Clasificación y controles de seguridad |
| Autorización escrita para usar el registro 2026 y estas respuestas | Director | Uso de datos reales en el piloto |
| Plazos legales por tipo (peticiones de informe escrito, Contraloría, acceso a la información) con su norma | Asesoría legal | Cálculo de plazos legales; la respuesta recibida ("de uno a tres días, ampliables") no cita norma |
| Guía de fiscalización y cláusulas de los contratos vigentes | Fiscales | Reglas de órdenes de cambio y contratos modificatorios (fase 3) |
| Base de datos de los 44 institutos que armó el programa de equipamiento | Responsable de equipamiento (CODAN) | Evitar dos bases paralelas con la del consolidado |
| Copias de Formularios de Asignación y Actas de Entrega (Decreto 100, art. 27) | Unidad de Manejo de Bienes | Pestaña Dotación de la ficha del instituto |
| Qué es el sistema "SGP's" de reporte del POA | Coordinación de educación | Enlace con POA (fase 6) |
| Calendario de feriados nacionales y departamentales | Recursos Humanos | Cálculo de días hábiles |

Cuestionarios no recibidos: ninguno de los ocho modelos quedó sin respuesta, pero el de Sistemas no lo respondió la unidad correcta.
