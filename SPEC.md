# Especificación técnica — Sistema de Gestión Documental y Correspondencia (piloto DDGS)

Versión 0.1 · 16/11/2026 · Estado: borrador para construir el prototipo

Este documento es la fuente de verdad del prototipo. Si algo no está aquí, se pregunta antes de inventarlo.

---

## 1. Contexto

La Dirección de Desarrollo y Gestión Social (DDGS) del Gobierno Autónomo Departamental de La Paz registra hoy su correspondencia en 8 hojas Excel (NIN, NEX, INF, MEM, INST, COM, HR, OS). El diagnóstico 2026 encontró:

- 1.219 documentos en 10,5 meses (≈ 5,4 por día hábil); unos 20 usuarios.
- 253 números de CITE sin documento (reservados, anulados o vacíos).
- Solo 40–68 % de los documentos vinculados a una hoja de ruta (HR).
- 29 % de referencias sin objeto ("REMITO INFORME").
- Nombres de personas en texto libre; la dirección cambió de titular 3 veces en el año.
- Sin estado, plazo ni fecha de respuesta: no se pueden medir pendientes.

El sistema es un **piloto para la DDGS** que luego debe extenderse a **toda la Gobernación** sin reescribirse.

## 2. Objetivo del prototipo

Reemplazar el Excel en la DDGS con un sistema web que:

1. Numere CITE automáticamente al firmar (sin reservas en blanco).
2. Vincule todo documento a un expediente con HR (o marcado "de oficio").
3. Derive el trabajo a **cargos** (no a personas) con plazo y bandeja.
4. Guarde el PDF de cada documento con su hash.
5. Registre todo en una bitácora inmutable.
6. Exponga una API REST y una tabla de eventos para integraciones futuras (IA, X-Road/AGETIC, obras, POA).

### 2.1 Dentro del alcance (MVP)

- Catálogos: unidades, cargos, personas, ocupación de cargos, instituciones externas, proyectos, procesos, tipos de documento.
- Expedientes, documentos, destinatarios, adjuntos, derivaciones.
- Flujo: recepción → derivación → elaboración → revisión → firma (CITE) → despacho → archivo.
- Envío masivo: en comunicados, instructivos y circulares, un CITE con lista de destinatarios; en notas personalizadas, un CITE por destinatario (configurable por tipo). Seguimiento de quién respondió.
- Registro de garantías de obra con alertas a 15 y 5 días (adelanto de la fase 3).
- Ajustes del levantamiento de noviembre de 2026: ver `docs/levantamiento-2026-11.md` §2 (A1-A18). En caso de conflicto, ese documento prevalece sobre esta especificación hasta que se integre aquí.
- Bandeja por cargo, búsqueda, tablero básico.
- Bitácora inmutable y outbox de eventos.
- Importación del Excel histórico 2026 (comando de gestión).
- Módulo **Institutos**: catálogo de los 44 institutos, mapa con filtros, ficha integral (proyectos, inversiones, estado legal, matrícula, correspondencia) y captura de ubicación. Detalle en `docs/modulo-institutos.md`.
- Despliegue con Docker Compose.

### 2.2 Fuera del alcance (fases posteriores)

- Firma digital criptográfica del PDF (fase 2; el MVP registra "firmado por" + PDF subido).
- Módulo de obras (planillas, garantías con alertas), POA, activos (fase 3+). La ficha del instituto muestra proyectos y dotación como registros simples hasta entonces.
- Búsqueda vectorial e IA (fase 4; dejar pgvector disponible).
- Interoperabilidad entre instituciones (fase 5; solo dejar el endpoint detrás de bandera).
- Login con Ciudadanía Digital / OIDC (dejar preparado, no implementar).

## 3. Decisiones de arquitectura (ADR resumidos)

| # | Decisión | Motivo |
| --- | --- | --- |
| ADR-01 | **Monolito modular** (un despliegue, apps Django con límites claros), no microservicios | 20 usuarios, ~1.500 docs/año, equipo pequeño. Un módulo se separa solo si un equipo propio o una carga distinta lo exige. |
| ADR-02 | **Django 5.2 LTS** + Django REST Framework + plantillas Django con **HTMX** | Admin incluido para catálogos, ORM y migraciones maduras, UI sin SPA = menos piezas que mantener. 5.2 LTS tiene soporte de seguridad hasta abril 2028; planificar migración a 6.2 LTS (abril 2027). |
| ADR-03 | **PostgreSQL 17 con extensión pgvector 0.8.x** (imagen `pgvector/pgvector:pg17`) | Una sola base para datos y vectores: los filtros de permisos y de proyecto se aplican en la misma consulta que la búsqueda semántica (pgvector 0.8 mejoró el filtrado con escaneo iterativo de índices HNSW). Sin base vectorial separada salvo ADR con medición. |
| ADR-04 | **Almacenamiento de objetos con API S3**, autoalojado con **SeaweedFS** (alternativa: Garage). **No usar MinIO Community** | MinIO Community dejó de publicar imágenes Docker en oct-2025 y su repositorio fue archivado en 2026. Con API S3 se puede migrar a otro proveedor cambiando solo variables de entorno (`django-storages` + `boto3`). |
| ADR-05 | **Outbox transaccional** en PostgreSQL + proceso `worker` | Eventos confiables sin Redis/Kafka. El worker procesa la tabla. |
| ADR-06 | **Bitácora append-only** con trigger de PostgreSQL que bloquea UPDATE/DELETE | Auditoría que ni el administrador de la app puede alterar desde el ORM. |
| ADR-07 | **Multi-unidad desde el día 1** | Cada tabla de negocio lleva `unidad`; extender a otra dirección es configuración. |
| ADR-08 | Software libre y estándares abiertos | Alineado al PISLEA (DS 5309/2025), opcional para entidades territoriales pero recomendable. |

## 4. Estructura del repositorio

```
.
├── SPEC.md                  # este documento
├── CLAUDE.md                # instrucciones para Claude Code
├── docker-compose.yml       # entorno local y de piloto
├── .env.example
├── Dockerfile               # (a crear)
├── pyproject.toml           # (a crear) dependencias (uv + uv.lock), ruff, pytest
├── SECURITY.md              # reporte de vulnerabilidades
├── manage.py
├── config/                  # settings (base, dev, prod), urls, wsgi/asgi
├── apps/
│   ├── core/                # unidades, cargos, personas, ocupaciones, instituciones, proyectos, procesos
│   ├── correspondencia/     # expedientes, documentos, destinatarios, derivaciones, CITE, envíos masivos
│   ├── archivos/            # adjuntos, hash, almacenamiento S3
│   ├── seguridad/           # autenticación, 2FA, permisos puede(), clasificación, sesiones (docs/seguridad.md)
│   ├── auditoria/           # bitácora (append-only)
│   ├── eventos/             # outbox + worker
│   ├── importacion/         # importador del Excel histórico
│   ├── api/                 # DRF: routers, serializers, permisos
│   └── tablero/             # vistas de indicadores
├── templates/               # Django + HTMX
├── static/
├── scripts/                 # backup.sh, restore.sh, init_s3.sh
├── seeds/                   # datos SINTÉTICOS (nunca datos reales)
└── tests/
```

Regla de módulos: una app solo accede a modelos de otra a través de su `services.py` o de claves foráneas; nunca escribe directamente en tablas ajenas.

## 5. Modelo de datos

Convenciones: PK `id` bigint; `creado_en`/`actualizado_en` en todas las tablas de negocio; nombres en español; `TextChoices` para estados.

### 5.1 core

**Unidad**
- `sigla` (único, ej. `DDGS`), `nombre`, `padre` (FK Unidad, nulo), `prefijo_cite` (ej. `GADLP/SDGS/DDGS`), `activo`.

**Cargo**
- `unidad` (FK), `codigo` (único), `nombre` (ej. "Director(a)", "Fiscal de obras 1"), `puede_firmar` (bool), `es_ventanilla` (bool), `activo`.

**Persona**
- `usuario` (OneToOne a `User`, nulo para personas sin acceso), `nombres`, `apellidos`, `nombre_corto` (ej. "Ing. M. N."), `profesion`, `email`, `activo`.

**OcupacionCargo**
- `persona` (FK), `cargo` (FK), `tipo` ∈ {`titular`, `interino`, `suplente`}, `desde` (date), `hasta` (date, nulo = vigente), `acto_designacion` (texto: memorándum/resolución).
- Restricción: como máximo un `titular` vigente por cargo (constraint parcial o validación en servicio).
- Servicio clave: `cargos_vigentes(persona, fecha=hoy)`.

**InstitucionExterna**
- `codigo` (único; será la dirección de envío en interoperabilidad), `tipo` ∈ {`gam`, `instituto`, `contratista`, `supervision`, `ministerio`, `entidad_departamental`, `otra`}, `nombre`, `sigla`, `autoridad_nombre`, `autoridad_cargo`, `municipio`, `activo`.

**Proyecto**
- `codigo` (único), `nombre`, `instituto` (FK InstitucionExterna, nulo), `municipio`, `contrato_ref` (ej. `LPN/34/2025`), `codigo_sisin` (nulo), `estado` ∈ {`preinversion`, `contratacion`, `ejecucion`, `recepcion`, `cerrado`}, `cargo_fiscal` (FK Cargo, nulo), `unidad` (FK).

**Proceso**
- `codigo`, `nombre`, `padre` (FK, nulo), `requiere_proyecto` (bool), `plazo_dias_defecto` (int).
- Semilla (8): Ejecución de obras* · Personal y consultores · Información, control y legal · Preinversión, POA y presupuesto · Comisiones y logística · Contrataciones y adquisiciones · Regulación de institutos técnicos · Programas (CODAN, Ayni, dotación). (*`requiere_proyecto=True`).

### 5.2 correspondencia

**TipoDocumento**
- `codigo` (NIN, NEX, INF, MEM, INST, COM, OS), `nombre`, `ambito` ∈ {`interno`, `externo`}, `activo`.

**SecuenciaCite**
- `unidad`, `tipo`, `anio`, `ultimo` (int). `unique(unidad, tipo, anio)`.

**Expediente**
- `unidad` (FK), `numero_hr` (texto, nulo), `de_oficio` (bool), `asunto`, `proceso` (FK), `proyecto` (FK, nulo), `origen` ∈ {`interno`, `externo`}, `remitente_institucion` (FK, nulo), `remitente_unidad` (FK Unidad, nulo), `estado` ∈ {`abierto`, `en_tramite`, `en_espera`, `cerrado`, `anulado`}, `cargo_responsable` (FK Cargo), `fecha_limite` (date, nulo), `confidencial` (bool), `creado_por` (FK Persona).
- Restricciones: `numero_hr` obligatorio salvo `de_oficio=True`; `proyecto` obligatorio si `proceso.requiere_proyecto`; `unique(numero_hr)` cuando no es nulo (la HR es única en la Gobernación — confirmar con la Unidad de Sistemas; dejarlo configurable).

**Documento**
- `expediente` (FK), `tipo` (FK), `numero` (int, nulo hasta firmar), `anio` (int), `cite` (texto único, nulo hasta firmar), `asunto`, `resumen` (texto), `elaborado_por` (FK Persona), `cargo_firmante` (FK Cargo), `firmado_por` (FK Persona, nulo), `fecha_firma` (datetime, nulo), `estado` ∈ {`borrador`, `en_revision`, `observado`, `reservado`, `firmado`, `despachado`, `anulado`}, `responde_a` (FK Documento, nulo), `reserva_expira_en` (datetime, nulo), `motivo_anulacion` (texto), `envio_masivo` (FK, nulo), `historico` (bool, para importados).

**Destinatario**
- `documento` (FK), `tipo` ∈ {`unidad`, `cargo`, `institucion`}, `unidad`/`cargo`/`institucion` (FK, uno no nulo según tipo), `atencion` (texto libre opcional: "Ing. …, Alcalde").

**EnvioMasivo**
- `nombre`, `tipo` (FK TipoDocumento), `asunto`, `plantilla` (FK Adjunto), `creado_por`, `estado`.
- Al firmar genera un `Documento` por destinatario, cada uno con su CITE.

**Derivacion**
- `expediente` (FK), `de_cargo` (FK), `a_cargo` (FK), `proveido` (texto), `instruccion` ∈ {`conocimiento`, `informe`, `respuesta`, `revision`, `archivo`}, `fecha` (datetime), `fecha_limite` (date), `atendida_en` (datetime, nulo), `documento_respuesta` (FK Documento, nulo), `estado` ∈ {`pendiente`, `atendida`, `devuelta`}. "Vencida" se calcula (`pendiente` y `fecha_limite < hoy`).

### 5.3 archivos

**Adjunto**
- `documento` (FK, nulo si es plantilla de envío), `archivo` (FileField en storage S3), `nombre_original`, `mime`, `tamano`, `sha256` (calculado al subir, indexado), `es_principal` (bool), `texto_extraido` (texto, nulo; para fase IA), `subido_por`, `subido_en`.
- Ruta de almacenamiento: `{unidad}/{anio}/{tipo}/{cite_o_uuid}/{sha256}.{ext}`.
- Tipos permitidos: PDF (principal), DOCX, XLSX, JPG/PNG. Tamaño máximo configurable (por defecto 25 MB).

### 5.4 auditoria

**Bitacora** (append-only)
- `actor` (FK User, nulo para sistema), `accion` (texto), `objeto_tipo`, `objeto_id`, `antes` (JSONB), `despues` (JSONB), `ip`, `creado_en`.
- Migración con trigger PostgreSQL que lanza excepción en `UPDATE` o `DELETE`.
- Toda transición de estado y toda edición de catálogos escribe aquí desde la capa de servicios.

### 5.5 eventos

**EventoOutbox**
- `tipo` (ej. `documento.firmado`), `agregado` (texto), `agregado_id`, `payload` (JSONB), `creado_en`, `procesado_en` (nulo), `intentos`, `ultimo_error`.
- Se inserta en la **misma transacción** que el cambio de negocio.
- Tipos mínimos: `expediente.creado`, `expediente.derivado`, `expediente.cerrado`, `documento.enviado_revision`, `documento.observado`, `documento.firmado`, `documento.despachado`, `documento.anulado`, `derivacion.vencida`, `adjunto.subido`.
- Consumidores del MVP: (a) marcar derivaciones vencidas y notificar por correo; (b) anular reservas vencidas; (c) placeholder de extracción de texto (no hace nada en MVP).

### 5.6 institutos

Entidades `Instituto`, `Ubicacion`, `AutoridadInstituto`, `ResolucionMinisterial`, `DerechoPropietario`, `Matricula`, `Carrera`, `TechoPresupuestario`; `Proyecto` (core) gana `instituto`, `tipo`, `presupuesto_bs`, `ejecutado_bs`, `estado` y `codigo_sisin`. Campos, reglas y mapa en `docs/modulo-institutos.md`. Lat/lon decimales; PostGIS solo con ADR.

## 6. Reglas de negocio

1. **CITE**: formato `{prefijo_cite}/{TIPO}-{numero}/{anio}`, ej. `GADLP/SDGS/DDGS/NIN-125/2026`. Se asigna **al firmar**, dentro de `transaction.atomic()` con `select_for_update()` sobre `SecuenciaCite` (crear la fila si no existe, también bloqueada). Prohibido calcular el siguiente número con `MAX()+1`.
2. **Reserva urgente**: el cargo firmante puede reservar un CITE (estado `reservado`) que expira a las 24 h (configurable). El worker anula automáticamente las reservas vencidas con motivo "reserva vencida".
3. **Anulación**: solo el cargo firmante o el administrador; motivo obligatorio (mín. 10 caracteres). El número no se reutiliza.
4. **Asunto**: mínimo 6 palabras; rechazar asuntos genéricos (lista configurable de expresiones, ej. `^(ref\.?:?\s*)?(remito|remite|remisión de) informe\.?$`, `^favor su atención`, `^su contenido$`, `^sirvase tener presente`). Mensaje de error que explique cómo redactarlo.
5. **Expediente**: HR obligatoria salvo "de oficio"; proceso obligatorio; proyecto obligatorio si el proceso lo requiere.
6. **Derivación**: siempre de cargo a cargo, con plazo (por defecto `proceso.plazo_dias_defecto` en días hábiles; feriados configurables en una tabla simple). La bandeja de una persona = derivaciones `pendiente` cuyo `a_cargo` está en sus `cargos_vigentes`, incluidas suplencias.
7. **Firma**: solo una persona con ocupación vigente en un cargo con `puede_firmar=True` igual a `cargo_firmante`. Requiere adjunto principal PDF.
8. **Despacho**: ventanilla registra fecha de despacho; para externos, se guarda constancia (texto o adjunto).
9. **Respuesta**: un documento con `responde_a` cierra automáticamente la derivación que originó la respuesta, si existe.
10. **Envío masivo**: según `TipoDocumento.cite_por_destinatario`: comunicados, instructivos y circulares llevan un solo CITE con lista de destinatarios; notas personalizadas, un CITE por destinatario. Queda agrupado por `EnvioMasivo` para no contaminar los indicadores y para seguir quién respondió.
11. **Confidencialidad**: expedientes `confidencial=True` solo visibles para cargos derivados, director(a) y auditoría.
12. **Histórico**: los documentos importados del Excel quedan `historico=True`, `estado=firmado`, con el CITE original, y **no** consumen la secuencia (inicializar `SecuenciaCite.ultimo` con el máximo importado por tipo).

## 7. Roles y permisos

| Rol (grupo Django) | Puede |
| --- | --- |
| `administrador` | Catálogos, usuarios, ocupaciones, configuración; ver todo. |
| `director` | Todo lo de técnico + derivar, firmar, anular, cerrar expedientes de su unidad. |
| `ventanilla` | Registrar entradas (HR), crear expedientes, despachar, archivar. |
| `tecnico` | Ver su bandeja, crear borradores, responder derivaciones, subir adjuntos. |
| `consulta` | Lectura de expedientes no confidenciales de su unidad. |
| `auditor` | Lectura total + bitácora; sin escritura. |

Los permisos de objeto se evalúan por **unidad** y por **cargos vigentes**, no por usuario fijo.

## 8. API REST (`/api/v1/`)

Autenticación: sesión (UI) y token (integraciones). Documentación OpenAPI con `drf-spectacular` en `/api/v1/docs/`. Paginación por cursor. Filtros con `django-filter`.

| Método y ruta | Descripción |
| --- | --- |
| `GET /catalogos/{unidades,cargos,personas,instituciones,proyectos,procesos,tipos}/` | Catálogos (escritura solo admin) |
| `GET/POST /expedientes/` · `GET/PATCH /expedientes/{id}/` | Expedientes |
| `POST /expedientes/{id}/derivar/` | Crear derivación |
| `POST /expedientes/{id}/cerrar/` | Cerrar |
| `GET/POST /documentos/` · `GET/PATCH /documentos/{id}/` | Documentos |
| `POST /documentos/{id}/enviar-revision/` · `/observar/` · `/firmar/` · `/despachar/` · `/anular/` · `/reservar/` | Transiciones |
| `POST /documentos/{id}/adjuntos/` | Subir adjunto (multipart) |
| `GET /bandeja/` | Derivaciones pendientes del usuario (por cargos vigentes) |
| `GET /buscar/?q=` | Búsqueda por CITE, HR, asunto, institución, proyecto (PostgreSQL full-text, config `spanish`) |
| `GET /eventos/?desde_id=` | Lectura del outbox para integraciones (solo token con permiso) |
| `POST /interop/recibir/` | **Detrás de bandera `INTEROP_HABILITADO=false`.** Recibe una cápsula (metadatos + PDF + sha256) con `Idempotency-Key`; responde `recibido`, `direccion_erronea` o `capsula_defectuosa`. |
| `GET /salud/` | Healthcheck (DB + storage) |

Las transiciones viven en `services.py` (no en views ni serializers) y son las mismas para UI y API.

## 9. Interfaz de usuario (Django + HTMX)

1. **Inicio / Bandeja**: pendientes por cargo, vencidas en rojo, por vencer (≤ 2 días) en ámbar.
2. **Registrar entrada** (ventanilla): HR, remitente (catálogo), asunto, proceso, proyecto, PDF escaneado → crea expediente y derivación al director.
3. **Expediente**: cabecera, línea de tiempo (desde bitácora), documentos, derivaciones, botón "Derivar".
4. **Documento**: metadatos, destinatarios (autocompletar desde catálogos), adjuntos, botones según estado y rol.
5. **Firma**: vista del PDF + confirmar → muestra el CITE asignado.
6. **Búsqueda** con filtros (tipo, proceso, proyecto, estado, fechas).
7. **Tablero**: documentos por mes y proceso, pendientes por cargo, vencidas, tiempo medio de atención por derivación.
8. **Admin Django** para catálogos y ocupaciones.
9. **Mapa de institutos** (Leaflet servido localmente; teselas propias o de OpenStreetMap con atribución) y **ficha integral** por pestañas, según `docs/modulo-institutos.md` §4-5.

Requisitos: español, accesible con teclado, usable en pantallas de 1366 px y en móvil para la bandeja. Sin dependencias de CDN en producción (servir estáticos localmente).

## 10. Importador del Excel histórico

Comando: `python manage.py importar_registro_excel --archivo RUTA.xlsx --anio 2026 --unidad DDGS --alias alias.csv [--dry-run]`

- Hojas: `NIN 2026`, `NEX 2026`, `INFORME 2026`, `MEMORANDUM 2026`, `INSTRUCTIVOS`, `COMUNICADO`, `H.R.`, `ORDENES DE SERVICIO` (fila de encabezado detectada automáticamente buscando "REFERENCIA").
- Filas con referencia vacía o que contengan `RESERVAD`, `ANULAD`, `COMPLETAR` → se reportan, no se importan como documentos (se cuentan en el informe).
- `alias.csv` (no versionado) mapea variantes de nombre → persona; lo no reconocido queda como `elaborado_por=NULL` y se lista en el informe.
- Proceso sugerido por reglas de palabras clave (configurables); marcado como `proceso_sugerido=True` para revisión.
- Salida: informe en consola + CSV con filas importadas, omitidas y sin autor.
- **Nunca** subir el Excel real ni `alias.csv` al repositorio (`.gitignore`).

## 11. Despliegue (Docker Compose)

Servicios (ver `docker-compose.yml`):

| Servicio | Imagen | Rol |
| --- | --- | --- |
| `db` | `pgvector/pgvector:pg17` | PostgreSQL con pgvector |
| `s3` | `chrislusf/seaweedfs` (fijar versión) | Almacenamiento de objetos S3 |
| `s3-init` | misma imagen o `amazon/aws-cli` | Crea el bucket al iniciar |
| `web` | build local | Django + gunicorn (migrate + collectstatic al arrancar) |
| `worker` | build local | `python manage.py procesar_eventos --loop` |
| `mailpit` | `axllent/mailpit` (perfil `dev`) | Correo de prueba |

- Configuración solo por variables de entorno (`.env`); nada de secretos en el repo.
- Healthchecks en `db`, `s3` y `web`.
- Volúmenes nombrados para DB y S3.
- Producción del piloto: un servidor (4 vCPU, 8 GB RAM, 200 GB) detrás de un proxy inverso con TLS (Caddy o nginx; fuera del compose base).

### 11.1 Respaldo

Respaldo cifrado en origen con `restic` hacia **uno o varios destinos a la vez**: disco/NAS, SFTP, AWS S3 y compatibles, Google Cloud Storage, Azure Blob, Backblaze B2 y, vía `rclone`, Dropbox, OneDrive o Google Drive. Servicio `backup` (perfil `backup`), metas RPO 24 h / RTO 4 h, custodia de claves y pruebas de restauración: ver **`docs/respaldos.md`**.

## 12. Calidad y pruebas

- `pytest` + `pytest-django`; cobertura ≥ 80 % en `services.py`.
- Pruebas obligatorias:
  1. **Concurrencia del CITE**: 20 firmas simultáneas del mismo tipo → números 1..20 sin huecos ni duplicados (usar `TransactionTestCase` + hilos o procesos).
  2. Firma rechazada si el usuario no ocupa el cargo firmante vigente.
  3. Suplente ve la bandeja del titular durante la suplencia y deja de verla al terminar.
  4. Asunto genérico rechazado.
  5. Expediente sin HR rechazado salvo "de oficio".
  6. Bitácora: `UPDATE`/`DELETE` fallan a nivel de base.
  7. Evento outbox creado en la misma transacción (si la transacción falla, no hay evento).
  8. Reserva vencida anulada por el worker.
  9. Importador en `--dry-run` con un Excel sintético de prueba (generado en el test).
  10. `/interop/recibir/` responde 404 con la bandera apagada e idempotente con la bandera encendida.
- `ruff` (lint + format), `mypy` opcional.
- CI en GitHub Actions: lint, tests con servicio PostgreSQL, build de imagen.

## 13. Seguridad

Ver **`docs/seguridad.md`** (módulo `apps/seguridad`). Resumen: OWASP ASVS 5.0 nivel 2 como estándar de verificación; alineación con el PISI de la Gobernación; 2FA obligatorio para roles privilegiados; autorización centralizada `puede(usuario, accion, objeto)` (RBAC + atributos de unidad, cargo y clasificación); clasificación público/interno/confidencial/reservado; archivos nunca públicos; bitácora de seguridad; controles automáticos en CI (bandit, pip-audit, gitleaks, trivy, `check --deploy`).

## 13 bis. Políticas de ingeniería

Ver **`docs/politicas-ingenieria.md`**: stack fijo y política de versiones, límites entre módulos (`services.py`/`selectors.py` + `import-linter`), Git y revisiones, CI bloqueante, migraciones *expand → contract*, versionado semántico, entornos, escalamiento por etapas, documentación como código y definición de terminado.

## 14. Criterios de aceptación del prototipo

1. `docker compose up` en una máquina limpia levanta todo y `/api/v1/salud/` responde 200.
2. Con los datos semilla, se puede recorrer el flujo completo: entrada con HR → derivación → borrador → revisión → firma (CITE asignado) → despacho → cierre.
3. La bandeja del suplente funciona según fechas de ocupación.
4. El tablero muestra pendientes y vencidas por cargo.
5. El importador procesa un Excel sintético con la misma estructura que el real y emite su informe.
6. Todas las pruebas del punto 12 pasan en CI.
7. `scripts/backup.sh` + `scripts/restore.sh` reconstruyen la base y los archivos en un entorno limpio.
8. Se cumplen los criterios de `docs/modulo-institutos.md` §9 con un Excel sintético de institutos.

## 15. Hoja de ruta posterior

| Fase | Contenido |
| --- | --- |
| 2 | Firma digital del PDF (certificados reconocidos en Bolivia), plantillas DOCX con CITE incrustado, OIDC (Keycloak / Ciudadanía Digital). |
| 3 | Módulo obras: planillas, órdenes de cambio, garantías con alertas, avance; enlace por código de proyecto con la plataforma técnico-económica que se use. |
| 4 | Extracción de texto/OCR, embeddings en pgvector, búsqueda semántica con permisos heredados, resúmenes de expediente. |
| 5 | Correspondencia entre instituciones (cápsula + recepción idempotente) vía Plataforma de Interoperabilidad de AGETIC o X-Road. |
| 6 | Vínculo con POA (operación por expediente) y trazabilidad de dotación/activos, referenciando SIGEP/SEGUIPOA/Activos Fijos por código. |

## 16. Producto reutilizable y entrega a la institución

El sistema se desarrolla como producto propio del proveedor, se entrega (cede o licencia) a la Gobernación y se sostiene con un contrato de mantenimiento. Por eso:

1. **Nada institucional en el código.** Nombre de la entidad, siglas, prefijo de CITE, logos, plantillas y textos legales se configuran en base de datos o variables de entorno (`INSTITUCION_NOMBRE`, `INSTITUCION_SIGLA`, logo cargable). El mismo código debe poder instalarse en otra gobernación o municipio sin cambios.
2. **Licencia explícita** en `LICENSE` según lo que se acuerde en el contrato (ver opciones en la nota comercial; por defecto AGPL-3.0 con titularidad del proveedor). Encabezado de copyright en cada archivo fuente.
3. **Paquete de entrega** (en `docs/`): manual de usuario por rol, manual técnico (arquitectura, modelo de datos, API), manual de instalación y actualización, procedimiento de respaldo y restauración, plan de continuidad, registro de cambios (`CHANGELOG.md`, versionado semántico).
4. **Versiones etiquetadas** (`v0.1.0`, …) y notas de versión por cada entrega, para facturar y aceptar entregas contra criterios verificables.
5. **Migraciones de datos reversibles** y probadas, para que las actualizaciones del contrato de mantenimiento sean de bajo riesgo.

## 17. Preguntas abiertas (no bloquean el prototipo)

- ¿La numeración de HR es única para toda la Gobernación? ¿Qué sistema la genera?
- Sigla vigente: ¿DDGS o DDS? Prefijo de CITE exacto.
- ¿Quién mantendrá el sistema (Unidad de Sistemas, consultoría, proveedor)?
- ¿Proveedor de certificados para firma digital?
- Política de retención documental (plazos de conservación por tipo).
