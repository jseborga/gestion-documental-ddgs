# Plan general del sistema (DDGS → Gobernación)

Versión 1.0 · 24/11/2026 · Prevalece sobre el orden de pasos de `CLAUDE.md` y sobre `SPEC.md` §15 donde difieran. Los ajustes del levantamiento (`docs/levantamiento-2026-11.md`, A1-A18) siguen vigentes.

## 1. Módulos

| # | Módulo | Estado | Alcance |
| --- | --- | --- | --- |
| M1 | **Correspondencia interna y externa** | En desarrollo (núcleo del demo) | Registro de entrada con HR de Ventanilla Única y fecha de ingreso a la Gobernación; derivación a cargos (varios destinos, proveído, acción, acuse digital); documentos con CITE al firmar; circulares con un CITE y seguimiento de respuestas; documentos relacionados; reservados; bandeja; búsqueda; informe de los lunes |
| M2 | **Documentos, firma y codificación** | En desarrollo | Plantillas por tipo; PDF generado con CITE y código de verificación (QR + huella SHA-256); firma en dos niveles (§3); reserva de CITE configurable |
| M3 | **Institutos georreferenciados** | En desarrollo | Vista en lista y en mapa; ficha por instituto (datos, estado legal, matrícula, carreras, proyectos vigentes, activos, correspondencia, inspecciones); trámites del Decreto Departamental 100 con requisitos y plazos (`docs/modulo-institutos.md`) |
| M4 | **Activos asignados a institutos** | Planificado | Seguimiento de bienes adquiridos, asignados, en uso, en desuso, revertidos y reasignados, con actas y código del registro oficial (§4) |
| M5 | **Proyectos y obras** | **Pendiente, se diseña aparte** | Presupuestos, precios unitarios y documentos de licitación (NB-SABS) quedan en el sistema de proyectos existente. Aquí, más adelante: avance, planillas, órdenes de cambio, contratos modificatorios, resolución de contratos, garantías con alertas, registro digital de supervisión y fiscalización. Mientras tanto, M1 y M3 solo guardan el proyecto como catálogo (código, instituto, estado, monto) y sus documentos |
| M6 | Tablero e indicadores | Con M1/M3 | Informe de los lunes, demora previa, pendientes por cargo, indicadores de institutos |
| M7 | Eventos y convocatorias | Planificado | Ferias (Expoferia CODAN), invitaciones masivas, inscripciones y jurados, apoyados en M1 |
| M8 | Inspecciones de campo | Planificado | Inspección técnica desde el celular (fotos, GPS, acta) vinculada a la ficha del instituto (DD 100 art. 8.d) |
| M9 | IA y búsqueda semántica | Futuro | Sobre pgvector, con permisos heredados |
| M10 | Interoperabilidad | Futuro | Plataforma de AGETIC o X-Road; SMAIL si expone datos |

## 2. Qué más incluir según el levantamiento

Además de lo que ya pide el plan, las entrevistas y cuestionarios justifican:

1. **Plantillas y listas de requisitos por trámite**: la falta de formatos es la causa más citada de observaciones (contrataciones e informes técnicos).
2. **Inspecciones de campo (M8)**: son función de la DDGS según el MOF 2027 y el Decreto 100; hoy no tienen registro.
3. **Base única de institutos**: el programa de equipamiento ya armó una base propia de los 44 institutos; hay que unificarla con la del consolidado.
4. **Eventos y convocatorias (M7)**: la Expoferia generó unas 30 invitaciones controladas a mano.
5. **Notificaciones por correo** de derivaciones y vencimientos; la difusión por WhatsApp queda como registro manual.
6. **Capacitación y manual por rol**: todo el personal tiene entre 9 días y 3 meses en el cargo.
7. **Funcionamiento en equipos lentos y celular**: hay equipos que no corren ni Word con fluidez.
8. **Garantías con alertas**: fue el pedido más fuerte de los fiscales. Queda en M5, pero es el primer candidato a adelantarse si M5 tarda.

## 3. Firma y codificación de documentos

| Nivel | Qué es | Validez | Cuándo |
| --- | --- | --- | --- |
| **N1. Firma registrada en el sistema** | El firmante confirma con su usuario y segundo factor; el sistema asigna el CITE, estampa la imagen de su firma (cargada por él y guardada protegida) y un sello con QR y código que lleva a una página de verificación (CITE, fecha, firmante, huella SHA-256 del PDF). Todo queda en la bitácora | Da trazabilidad y permite detectar alteraciones. **La imagen sola no prueba autoría**: cualquiera puede copiarla. Su uso interno necesita que la MAE lo disponga y un reglamento (respuesta de Asesoría Legal). No reemplaza la firma manuscrita ni la digital | Demo y piloto |
| **N2. Firma digital con certificado** | Firma PAdES del PDF con certificado de una entidad certificadora autorizada (ADSIB es la entidad pública) | Ley 164, art. 78: validez jurídica y probatoria | Fase posterior; requiere certificados para cada firmante, decisión de la MAE y reglamento |

Reserva de CITE: desactivada por defecto (decisión del Director); si se activa, máximo 24 h con anulación automática registrada.

## 4. Activos (M4): alcance y límite

El Decreto Departamental 100 asigna el registro oficial de activos a la Secretaría de Economía y Finanzas en el sistema vSIAF (Disposición Final Segunda) y la asignación a los institutos a la Unidad de Manejo de Bienes con Formulario de Asignación y Acta de Entrega (art. 27). La Dirección **coadyuva** en el control.

Por eso M4 **no es un segundo registro oficial**: es el seguimiento de la Dirección, enlazado por el código de activo del registro oficial.

- Entidades: `Activo` (código oficial, descripción, categoría, valor, fecha de compra, proyecto o proceso de origen), `MovimientoActivo` (adquisición, asignación, reversión, reasignación, baja; con acta adjunta), `VerificacionActivo` (fecha, estado: en uso, en desuso, dañado, no encontrado; foto; responsable).
- Vista por instituto: bienes comprados, en uso y en desuso; historial de entregas (art. 26-27 y 32).
- Importación desde los reportes del registro oficial cuando Manejo de Bienes los entregue.

## 5. Orden de desarrollo para el demo

| Etapa | Contenido | Resultado visible |
| --- | --- | --- |
| **D1. Seguridad antes de datos reales** | Paso 2b (doble factor, bloqueo por intentos, sesiones, permisos `puede()`), paso 3 (bitácora inalterable y eventos) y **respaldo diario mínimo** de base y archivos | Se puede cargar información real |
| **D2. Institutos en lista y mapa** | Modelos de M3, importación de los dos Excel de institutos **en el servidor** (no en GitHub), lista con filtros, mapa Leaflet, ficha por pestañas, captura de ubicación | Primera demostración al Director |
| **D3. Correspondencia** | Pasos 4, 5 y 7: archivos, flujo completo, bandeja, tablero; importación del registro 2026 | Uso diario del piloto |
| **D4. Documentos y firma N1** | Plantillas, PDF con CITE, QR de verificación e imagen de firma | Documentos emitidos desde el sistema |
| **D5. Activos (M4)** | Registro, movimientos, verificaciones, vista por instituto | Seguimiento de dotación |
| D6 | API completa (paso 6), respaldos completos multi-destino (paso 9), manuales (paso 10) | Entrega formal |
| Después | M7, M8, M5 (diseño aparte), N2, M9, M10 | — |

## 6. Datos reales en el demo

El Director autorizó usar los datos existentes para el demo. Reglas:

1. **Nunca en GitHub.** Los Excel y cualquier dato real se cargan directamente en el servidor (carga por el panel de administración o comando dentro del contenedor). `.gitignore` y la CI lo vigilan.
2. **Antes de cargar** (D1 terminado):
   - recrear la base con claves propias (hoy tiene la de ejemplo);
   - poner HTTPS al panel de EasyPanel;
   - doble factor para administradores;
   - respaldo diario funcionando.
3. **Datos mínimos.** Los teléfonos de los rectores no se cargan; los nombres del personal solo en el catálogo de personas, con acceso restringido.
4. **Cuentas individuales.** Sin usuarios compartidos; se desactivan al terminar el demo.
5. **Ubicación del servidor.** Si el servidor del demo está fuera de Bolivia, dejarlo dicho por escrito en la autorización. Producción irá donde apruebe la Unidad de Sistemas (levantamiento A16).
6. **Autorización por escrito** archivada con el proyecto.

## 7. Coordenadas de los institutos

Los Excel no tienen coordenadas. Para el demo hay dos caminos, que se pueden combinar:

1. Capturarlas con la hoja `Ubicaciones` del consolidado (enlace a Google Maps por fila) y luego importarlas.
2. Ubicación **aproximada** por localidad o municipio con el servicio de búsqueda de OpenStreetMap (Nominatim), marcada como `aproximada_localidad` y con contorno discontinuo en el mapa, para corregirla después desde la ficha.

Nunca se presenta una ubicación aproximada como exacta.
