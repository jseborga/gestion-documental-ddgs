# Módulo Institutos: mapa y ficha integral

Versión 0.1 · 24/11/2026 · Forma parte de `SPEC.md` (§5.6 y §9).

## 1. Para qué

La Dirección atiende 44 institutos técnicos tecnológicos (39 sedes y 5 subsedes, unos 24.600 estudiantes a julio de 2026) repartidos en 7 regiones del departamento. Hoy su información vive en dos Excel con texto libre. El módulo permite:

1. Ver todos los institutos en un **mapa** del departamento, con colores según su situación (obra paralizada, obra en ejecución, derecho propietario pendiente).
2. Entrar desde el mapa a la **ficha integral** de cada instituto: datos generales, proyectos e inversiones, dotación, estado legal, matrícula, oferta académica y su correspondencia.
3. Ser la **fuente única** del catálogo de institutos que usan correspondencia, obras, dotación y POA.

## 2. Datos de partida (diagnóstico de los Excel recibidos)

| Tema | Situación encontrada |
| --- | --- |
| Coordenadas | **Ninguna.** Solo direcciones en texto. Se capturan con la hoja `Ubicaciones` del consolidado y luego en el propio sistema. |
| Proyectos | 21 obras (8 construcciones por Bs 59,3 millones, 13 refacciones por Bs 4,5 millones) y equipamiento de un solo instituto (Bs 11,1 millones en 3 gestiones). 28 institutos sin ningún proyecto registrado 2021-2026. |
| Estados de obra | 3 en ejecución, 1 paralizada (con análisis de resolución de contrato), 3 concluidas sin cierre financiero, 1 con acta de entrega provisional. |
| Derecho propietario | 16 a nombre del GADLP; 27 en proceso (13 con folio real, 14 sin antecedentes); 1 sin dato. |
| Calidad | 12 observaciones: folios reales repetidos entre institutos distintos, un proyecto con nombre de otro instituto, provincia y municipio invertidos, techos presupuestarios ilegibles, años de equipamiento escritos en una fila de datos. |

Las cifras salen del consolidado `Institutos_DDGS_consolidado.xlsx` (fórmulas recalculables). El archivo real no se sube al repositorio.

## 3. Modelo de datos (`apps/institutos`)

| Entidad | Campos clave | Notas |
| --- | --- | --- |
| **Instituto** | `institucion` (OneToOne a `InstitucionExterna` tipo `instituto`), `codigo`, `nombre`, `sigla`, `sede_principal` (FK a sí mismo, nulo = sede), `region`, `provincia`, `municipio`, `direccion`, `dependencia` (fiscal, convenio, privado), `situacion` (en funcionamiento, cerrado, en apertura) | Las subsedes apuntan a su sede |
| **Ubicacion** | `instituto`, `lat`, `lon` (decimal 9,6), `precision` (gps_sitio, verificada_mapa, aproximada_localidad, pendiente), `fuente`, `capturado_por`, `fecha`, `foto_fachada` (adjunto, opcional) | Historial: la vigente es la última verificada |
| **AutoridadInstituto** | `instituto`, `nombre`, `cargo` (rector, responsable), `telefono`, `desde`, `hasta` | **Dato personal**: visible solo para roles internos |
| **ResolucionMinisterial** | `instituto`, `numero`, `anio`, `fecha`, `objeto` (funcionamiento, ampliación de carrera, otra), `adjunto` | |
| **DerechoPropietario** | `instituto`, `estado` (a_nombre_gadlp, en_proceso_con_folio, en_proceso_sin_antecedentes, otro), `folio_real`, `titular`, `anio`, `observaciones`, `adjuntos` | Restricción: un folio real no puede repetirse entre institutos sin justificación registrada |
| **Matricula** | `instituto`, `anio`, `mes`, `estudiantes`, `fuente` | Serie histórica, no un solo número |
| **Carrera** | `instituto`, `nombre`, `nivel` (técnico medio, técnico superior), `resolucion`, `vigente` | |
| **TechoPresupuestario** | `instituto`, `gestion`, `monto_bs`, `fuente` | |
| **Proyecto** (ya existe en `core`) | se agrega `instituto` (FK), `tipo` (construccion, refaccion, equipamiento, estudio), `gestion_inicio`, `gestion_fin`, `presupuesto_bs`, `ejecutado_bs`, `estado` (preinversion, contratacion, en_ejecucion, paralizada, recepcion_provisional, recepcion_definitiva, concluida_sin_cierre_financiero, cerrada), `codigo_sisin` | El detalle de obra (planillas, garantías) llega en la fase 3 |
| **Dotacion** (fase activos) | `instituto`, `fecha`, `acta`, `items`, `monto_bs`, `codigos_activo` | Referencia el inventario oficial de Activos Fijos por código |

Regla: los indicadores de la ficha (inversión total, proyectos por estado) se **calculan** desde estas tablas; nunca se escriben a mano.

## 4. Mapa

- **Biblioteca:** Leaflet (licencia BSD-2), servida desde los estáticos del sistema (sin CDN en producción).
- **Mapa base, en orden de preferencia:**
  1. Teselas propias servidas desde el servidor de la Gobernación (archivo único de teselas vectoriales del departamento, por ejemplo en formato PMTiles). Funciona sin depender de terceros.
  2. Teselas de OpenStreetMap con su atribución obligatoria, respetando su política de uso (tráfico bajo, sin descarga masiva). Válido para el piloto de 20 usuarios.
- **Capas y filtros:** región, provincia, municipio; estado de obra; derecho propietario; con o sin proyecto; sede o subsede.
- **Símbolos:** color según la situación más crítica del instituto: rojo = obra paralizada; ámbar = obra en ejecución o concluida sin cierre financiero; gris = derecho propietario sin antecedentes; verde = sin pendientes. Un contorno discontinuo indica ubicación aproximada.
- **Ubicación pendiente:** los institutos sin coordenadas aparecen en una lista lateral "sin ubicar" y en el centro de su municipio solo si se marca expresamente como aproximada.
- **Captura de ubicación** desde la ficha (rol técnico o superior):
  1. clic sobre el mapa;
  2. pegar coordenadas o un enlace de Google Maps (el sistema extrae lat/lon);
  3. en celular y con HTTPS, botón "usar mi ubicación" para visitas de campo (precisión GPS en sitio).
  Cada cambio queda en bitácora.
- **Datos geográficos:** `lat`/`lon` decimales bastan para 44 puntos. PostGIS solo con un ADR si se necesitan análisis espaciales (distancias, polígonos municipales).

## 5. Ficha integral del instituto

Pestañas:

1. **Resumen:** foto, dirección, mapa pequeño, autoridad, estudiantes (con tendencia), carreras, alertas (obra paralizada, garantía por vencer, derecho propietario pendiente).
2. **Proyectos e inversiones:** línea de tiempo 2021 en adelante con cada proyecto, monto, estado y enlace a su expediente; totales por tipo.
3. **Dotación:** entregas con actas y códigos de activo.
4. **Estado legal:** resolución ministerial, derecho propietario, documentos adjuntos, observaciones abiertas.
5. **Correspondencia:** expedientes y documentos vinculados al instituto (por destinatario, remitente o proyecto).
6. **Historial:** bitácora de cambios de la ficha.

## 6. API

| Método y ruta | Descripción |
| --- | --- |
| `GET /api/v1/institutos/` | Lista con filtros (región, provincia, estado) |
| `GET /api/v1/institutos/geojson/` | `FeatureCollection` para el mapa (sin datos personales) |
| `GET /api/v1/institutos/{id}/` | Ficha completa según permisos |
| `POST /api/v1/institutos/{id}/ubicacion/` | Registrar ubicación (lat, lon, precisión, fuente) |

## 7. Importación inicial

Comando `python manage.py importar_institutos --datos DATOS.xlsx --ficha FICHA.xlsx [--ubicaciones CONSOLIDADO.xlsx] [--dry-run]`:

- Une ambos archivos por N°, separa proyectos múltiples de una misma celda, convierte montos con formato boliviano (`15.054.108,05`), clasifica estados y derecho propietario.
- Importa las coordenadas capturadas en la hoja `Ubicaciones` del consolidado.
- Emite el informe de observaciones (folios repetidos, nombres que no coinciden, montos ilegibles) y no importa como válido lo dudoso: lo marca para revisión.
- Prueba automatizada con un Excel sintético de la misma estructura.

## 8. Indicadores del tablero

Inversión por región y por estudiante; proyectos por estado; institutos con obra paralizada o sin cierre financiero; derecho propietario por estado; institutos sin proyectos en el periodo; ubicaciones pendientes; matrícula por región y su tendencia.

## 9. Criterios de aceptación

1. Los 44 institutos se importan desde los Excel reales con el informe de observaciones.
2. El mapa muestra todos los institutos con coordenadas, filtra por región y estado, y abre la ficha al hacer clic.
3. La ficha muestra proyectos, inversiones, estado legal y correspondencia vinculada, con totales calculados.
4. Un técnico puede fijar o corregir la ubicación desde el celular, y el cambio queda en bitácora.
5. El GeoJSON público del mapa no contiene teléfonos ni nombres de autoridades.

## 10. Trámites del Decreto Departamental 100 (2017)

Base normativa del módulo: la Disposición Final Tercera encarga a la Dirección una base de datos de institutos fiscales y de convenio "con el objeto de contar con mecanismos de control". Vigencia y equivalencia de nombres de unidades **a confirmar** (ver `docs/levantamiento-2026-11.md` §6).

Cada trámite se carga como `TipoTramite` (requisitos como lista de verificación, etapas con plazo y tipo de días). Los plazos son los del texto recibido:

| Trámite | Artículos | Etapas y plazos |
| --- | --- | --- |
| Certificación de Factibilidad Técnica: apertura de instituto fiscal | 11-13 | Verificación de requisitos 5 días hábiles → inspección → informe técnico 10 días hábiles tras la inspección → informe legal de la Secretaría → Resolución Secretarial 5 días hábiles. Subsanación: 15 días hábiles o se tiene por desistida |
| Certificación de Factibilidad Técnica: ampliación de carreras | 14-16 | Verificación 10 días hábiles → inspección → informe técnico 10 días hábiles → informe legal → Resolución Secretarial o nota de rechazo 5 días hábiles. Subsanación 15 días hábiles. Institutos de convenio: según su convenio |
| Servicios básicos | 18-19 | Verificación de requisitos y remisión a Economía y Finanzas. Sin plazos fijados |
| Infraestructura: construcción, refacción, ampliación | 20-22 | Verificación → inspección en 20 días hábiles → informe de factibilidad técnica, social y económica en 30 días calendario → aprobación e informe legal de la Secretaría 5 días hábiles → programación presupuestaria → Informe Técnico de Condiciones Previas aprobado por la MAE |
| Equipamiento y mobiliario | 25-26 | Verificación 5 días hábiles; subsanación 15 días calendario o no presentada → informe de viabilidad (total o parcial) o rechazo en 20 días hábiles → aprobación de la Secretaría → la Dirección es Unidad Solicitante de la contratación |
| Asignación de activos al instituto | 27 | Solicitud de la Dirección → Unidad de Manejo de Bienes: Formulario de Asignación de Activos codificados y Acta de Entrega firmada por la MAE del instituto → copia legalizada a la Dirección. Reversión y reasignación con informes técnico y legal |
| Material educativo | 30-32 | Informe de viabilidad en 15 días hábiles → aprobación de la Secretaría → contratación → entrega por Almacén Central con Acta de Entrega de Material → descargos del instituto |

**Regla de elegibilidad (art. 20.II):** para proyectos de inversión el GADLP debe tener el derecho propietario registrado en Derechos Reales y en catastro municipal. Si no, solo cabe un convenio interinstitucional con plazos de saneamiento (art. 24.III). La ficha muestra el indicador "Apto para inversión en infraestructura" calculado desde `DerechoPropietario`. Contraste con los datos actuales: los 21 proyectos de construcción y refacción registrados 2021-2025 están en institutos con derecho propietario a nombre del GADLP; los 28 institutos sin ese registro no tienen obras registradas.

**Requisitos que se repiten** en casi todos los trámites y conviene guardar una sola vez en la ficha (con vigencia): designación de la máxima autoridad ejecutiva del instituto, Resolución Ministerial de apertura y funcionamiento, Folio Real a nombre del GADLP, certificado catastral y plano georreferenciado, Certificación de Factibilidad Técnica de apertura y, para institutos de convenio, el convenio vigente. Al iniciar un trámite, el sistema marca como cumplidos los requisitos que ya están vigentes en la ficha.
