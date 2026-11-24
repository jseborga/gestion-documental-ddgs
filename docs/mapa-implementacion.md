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
| P7 | Configuración de producción sin advertencias | `check --deploy` (en `verificar.sh`) |
| P8 | Sin datos reales ni secretos en el repositorio | `verificar.sh` (archivos de datos) + gitleaks en CI |
| P9 | Revisión de amenazas del paso (tabla §2) con cada riesgo mitigado o aceptado por escrito | Sección del paso en este documento |
| P10 | Permisos: toda vista nueva pasa por `puede()` y tiene prueba de acceso denegado | Pruebas del paso |
| P11 | Documentación y `CHANGELOG.md` actualizados | Revisión del diff |
| P12 | CI de GitHub en verde (incluye Docker Compose de punta a punta y respaldo/restauración) | Pestaña Actions |

`scripts/verificar.sh` ejecuta P2 a P8 de una vez; es lo mismo que corre la CI, para detectar fallas antes de subir.

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

### D2. Institutos en lista, mapa y ficha — **en curso**

| Paso | Contenido | Riesgos principales y mitigación |
| --- | --- | --- |
| D2.1 | Modelos: instituto, ubicación con historial, autoridad (dato personal), resolución ministerial, derecho propietario, matrícula por año, carreras, techo presupuestario, observaciones de calidad | Datos personales separados en su propia tabla y visibles solo para quien opera la unidad |
| D2.2 | Importador de los dos Excel (`importar_institutos`), con informe de observaciones y modo simulación | Archivo malicioso o enorme → límite de tamaño, solo `.xlsx`, lectura en modo solo valores, sin fórmulas ni macros; idempotente; todo en una transacción; bitácora |
| D2.3 | Lista con filtros y búsqueda | Paginación; filtros validados; permisos por `puede()` |
| D2.4 | Mapa (Leaflet servido localmente) y GeoJSON | GeoJSON sin teléfonos ni nombres de autoridades; CSP solo con el servidor de teselas configurado; sin CDN |
| D2.5 | Ficha por pestañas | Teléfono de la autoridad solo para roles operativos de la unidad; datos de proyectos de solo lectura (M5 pendiente) |
| D2.6 | Registro de ubicación (clic en mapa, coordenadas o enlace de Google Maps) y ubicación aproximada opcional por municipio (OpenStreetMap Nominatim) | Validación de rango geográfico; enlace analizado sin seguir redirecciones (sin SSRF); Nominatim solo desde un comando de administrador, con 1 petición por segundo; toda ubicación aproximada marcada como tal |
| D2.7 | Auditoría de la etapa y correcciones | Informe anexado a este documento |

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
