# Mapa de implementación

Versión 1.0 · 24/11/2026 · Complementa `docs/plan-general.md` (qué) con el cómo: pasos, puertas de control y evidencia. **Ningún paso se da por terminado sin pasar su puerta.**

## 1. Puerta de control de cada paso

Un paso queda terminado solo si cumple todo esto, en este orden:

| # | Control | Cómo se verifica |
| --- | --- | --- |
| P1 | Pruebas del paso escritas antes o junto con el código, incluidos los casos de error | `pytest` |
| P2 | Toda la suite en verde y cobertura ≥ 80 % en `services.py`, `selectors.py` y `apps/seguridad` | `scripts/verificar.sh` |
| P3 | Formato, lint y análisis estático sin hallazgos | ruff, bandit (en `verificar.sh`) |
| P4 | Dependencias sin vulnerabilidades conocidas | pip-audit (en `verificar.sh`) |
| P5 | Límites entre módulos respetados | import-linter (en `verificar.sh`) |
| P6 | Migraciones completas y reversibles | `makemigrations --check` + prueba de ida y vuelta |
| P7 | Configuración de producción sin advertencias y estáticos de producción generables (igual que el Dockerfile) | `check --deploy` y `collectstatic` (en `verificar.sh`) |
| P8 | Sin datos reales ni secretos en el repositorio | `verificar.sh` (archivos de datos) + gitleaks en CI |
| P9 | Revisión de amenazas del paso (tabla §2) con cada riesgo mitigado o aceptado por escrito | Sección del paso en este documento |
| P10 | Permisos: toda vista nueva pasa por `puede()` y tiene prueba de acceso denegado | Pruebas del paso |
| P11 | Documentación y `CHANGELOG.md` actualizados | Revisión del diff |
| P12 | CI de GitHub en verde (incluye Docker Compose de punta a punta y respaldo/restauración) | Pestaña Actions |

`scripts/verificar.sh` ejecuta P2 a P8 de una vez; es lo mismo que corre la CI, para detectar fallas antes de subir. **La puerta solo se considera superada si el script termina con código 0** (mensaje «Puerta superada»); nunca se juzga por una salida filtrada. Lección del 26/11/2026: la imagen Docker no se construyó porque `leaflet.js` referencia `leaflet.js.map`, que no se había copiado; la puerta no generaba los estáticos de producción. Se agregó ese paso a la puerta y a la CI. Lección del 24/11/2026: un commit se subió con dos líneas largas porque la salida se filtró y el código de salida no se comprobó; se corrigió en el commit siguiente.

## 2. Revisión de amenazas por paso (STRIDE abreviado)

Para cada pantalla, comando o integración nueva se responde:

| Amenaza | Pregunta |
| --- | --- |
| Suplantación | ¿Exige sesión y, si corresponde, segundo factor? |
| Manipulación | ¿Valida toda entrada en el servidor? ¿Usa formularios Django y ORM (sin SQL armado a mano)? ¿Protección CSRF? |
| Repudio | ¿Queda en la bitácora quién hizo qué y cuándo? |
| Divulgación | ¿Expone datos personales o clasificados? ¿Los endpoints públicos (GeoJSON, verificación) muestran solo lo mínimo? |
| Denegación de servicio | ¿Hay límites de tamaño, paginación o frecuencia? ¿Un archivo malicioso puede colgar el proceso? |
| Elevación de privilegios | ¿Puede un rol hacer más de lo que la matriz permite? ¿Hay prueba que lo niegue? |

## 3. Etapas y pasos

### D1. Seguridad antes de datos reales — **terminada** (pendiente desplegar)

| Paso | Contenido | Evidencia |
| --- | --- | --- |
| D1.1 | Bitácora inalterable y outbox | Trigger probado; 13 pruebas |
| D1.2 | Seguridad: `puede()`, segundo factor, bloqueo, sesiones, cabeceras, alertas | Matriz de 32 combinaciones; flujos completos |
| D1.3 | Respaldo diario cifrado y restauración segura | Respaldo y restauración reales en local; prueba en CI |
| D1.4 | Auditoría y correcciones | `docs/auditoria-2026-11-24.md`; 6 correcciones con pruebas de regresión |

### D2. Institutos en lista, mapa y ficha — **terminada** (pendiente desplegar)

| Paso | Contenido | Riesgos principales y mitigación |
| --- | --- | --- |
| D2.1 | Modelos: instituto, ubicación con historial, autoridad (dato personal), resolución ministerial, derecho propietario, matrícula por año, carreras, techo presupuestario, observaciones de calidad | Datos personales separados en su propia tabla y visibles solo para quien opera la unidad |
| D2.2 | Importador de los dos Excel (`importar_institutos`), con informe de observaciones y modo simulación | Archivo malicioso o enorme → límite de tamaño, solo `.xlsx`, lectura en modo solo valores, sin fórmulas ni macros; idempotente; todo en una transacción; bitácora |
| D2.3 | Lista con filtros y búsqueda | Paginación; filtros validados; permisos por `puede()` |
| D2.4 | Mapa (Leaflet servido localmente) y GeoJSON | GeoJSON sin teléfonos ni nombres de autoridades; CSP solo con el servidor de teselas configurado; sin CDN |
| D2.5 | Ficha por pestañas | Teléfono de la autoridad solo para roles operativos de la unidad; datos de proyectos de solo lectura (M5 pendiente) |
| D2.6 | Registro de ubicación (clic en mapa, coordenadas o enlace de Google Maps) y ubicación aproximada opcional por municipio (OpenStreetMap Nominatim) | Validación de rango geográfico; enlace analizado sin seguir redirecciones (sin SSRF); Nominatim solo desde un comando de administrador, con 1 petición por segundo; toda ubicación aproximada marcada como tal |
| D2.7 | Auditoría de la etapa y correcciones | §5 de este documento |

### D3 a D6

Se detallan al iniciar cada etapa con la misma estructura (pasos, riesgos, evidencia). Orden: D3 correspondencia → D4 documentos y firma N1 → D5 activos → D6 API, respaldo externo y manuales.

## 4. Despliegue conjunto (desde D1)

Se hace una sola vez cuando el usuario lo indique, siguiendo `docs/despliegue-easypanel.md`:

1. CI en verde para el commit a desplegar.
2. Cambio de la clave de PostgreSQL y variables nuevas (D1).
3. Despliegue y verificación de salud.
4. Segundo factor del administrador; códigos de recuperación guardados.
5. Respaldo manual y restauración de prueba.
6. Importación de institutos en modo simulación, revisión del informe y luego importación real (D2).
7. Revisión de la bitácora: inicio de sesión, respaldo e importación registrados.

## 5. Auditoría de la etapa D2 (24/11/2026)

**Puerta:** `scripts/verificar.sh` superada en cada paso (D2.1: 127 pruebas; D2.2: 144; D2.3-D2.6: 159; cierre: ver CHANGELOG). Cobertura ≥ 93 %. pip-audit, bandit, ruff, import-linter y `check --deploy` sin hallazgos.

### Revisión de amenazas

| Amenaza | Control aplicado | Evidencia |
| --- | --- | --- |
| Suplantación | Todas las vistas exigen sesión y, por el middleware, segundo factor si corresponde | `test_anonimo_redirige` |
| Manipulación | Formularios Django; ORM; CSRF en el registro de ubicación; enlaces de mapas leídos sin abrirlos; archivos de importación validados (extensión, firma ZIP, macros, tamaño, descompresión, filas) y XML con defusedxml | `TestArchivosNoValidos`, `TestParsearCoordenadas` |
| Repudio | Ubicaciones, instituciones, proyectos e importaciones en la bitácora; la importación guarda la huella SHA-256 de cada archivo | `test_importa_todo` |
| Divulgación | La visibilidad en SQL replica `puede(VER)`; GeoJSON sin autoridades ni teléfonos; datos personales solo para quien edita; nombres insertados como texto en el mapa | `test_visibilidad_sql_coincide_con_puede`, `test_geojson_sin_datos_personales`, `test_ficha_permisos_y_datos_personales`, `test_lista_solo_de_su_unidad_y_escapada` |
| Denegación de servicio | Paginación (50), búsqueda acotada (80 caracteres), lista de pendientes acotada (200), límites del importador, Nominatim con 1 petición/s, tiempo de espera y tamaño máximo de respuesta, expresiones sin retroceso cuadrático | `test_expresion_de_coordenadas_sin_retroceso_costoso` |
| Elevación de privilegios | Registrar ubicación exige `EDITAR`; ventanilla, consulta, auditor y otras unidades reciben 403; el admin del personal (dato personal) no lo ve el auditor | `test_registrar_ubicacion_permisos` |

### Hallazgos de la auditoría y estado

| # | Severidad | Hallazgo | Estado |
| --- | --- | --- | --- |
| 1 | Media | El importador guardaba los teléfonos de los rectores, en contra de la regla de datos mínimos del plan general (§6.3). | **Corregido**: no se cargan salvo `INSTITUTOS_CARGAR_TELEFONOS=True`; prueba en ambos sentidos. |
| 2 | Media (funcional) | Con `Referrer-Policy: same-origin` el navegador no envía Referer al servidor de teselas; OpenStreetMap lo exige y podría bloquear el mapa base. | **Corregido**: `strict-origin-when-cross-origin` (a otros sitios solo se envía el origen, sin la ruta). |
| 3 | Baja | Una expresión de coordenadas podía tardar en forma cuadrática con textos largos de espacios. | **Corregido** y con prueba de tiempo. |
| 4 | Baja | La heurística inicial marcaba un inmueble como «a nombre de la entidad» con solo tener folio real. | **Corregido** antes de publicar: patrones de texto configurables (`INSTITUTOS_TITULAR_PATRONES`). |
| 5 | Baja | `a_nombre_gadlp` fijaba la institución en el código (regla de producto reutilizable). | **Corregido** antes de publicar: `a_nombre_entidad`. |
| 6 | Informativo | El GeoJSON devuelve todos los institutos visibles sin paginar. | Aceptado: decenas o pocos cientos de puntos. Revisar si se amplía a toda la Gobernación. |
| 7 | Informativo | El texto de atribución del mapa base se inserta como HTML por Leaflet. | Aceptado: lo define el administrador del servidor por variable de entorno, no los usuarios. |

### Validación con los archivos reales

Simulación del importador con las dos planillas reales (sin guardar, sin subirlas a GitHub): 44 institutos, 24 proyectos, 152 carreras y 8 observaciones automáticas. Los agregados coinciden exactamente con el consolidado de noviembre: derecho propietario 16/13/14/1, 24.622 estudiantes, 5 subsedes, inversión Bs 74.961.755,50, techo 2026 Bs 6.250.165. La simulación detectó que el encabezado real dice «NOMBRE DEL INSTITUTO…»: se corrigió la detección y la planilla sintética de pruebas ahora usa ese encabezado. Las 4 observaciones escritas a mano en noviembre se cargan con `--observaciones-extra`.

### Vacíos

- El mapa no se probó en un navegador real en este entorno (sin navegador); se probó el HTML, el GeoJSON y las cabeceras. Verificar visualmente al desplegar.
- La consulta a Nominatim se probó con respuestas simuladas (sin red); probar con `--simular` en el servidor.
