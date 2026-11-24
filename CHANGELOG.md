# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado semántico.

## [Sin publicar]

### Añadido (etapa D2: institutos)
- Modelos de institutos con ubicación e historial, autoridades (dato personal), resoluciones, derecho propietario (indicador de aptitud para inversión, DD 100 art. 20.II), matrícula, carreras, techos y observaciones de calidad.
- `importar_institutos`: planilla de datos y ficha técnica, con simulación, informe, huellas SHA-256 y defensas contra archivos maliciosos.
- Lista con filtros y semáforo, mapa con Leaflet local, GeoJSON sin datos personales, ficha por secciones y registro de ubicación (coordenadas, enlace de Google Maps o clic).
- `aproximar_ubicaciones`: ubicación aproximada por municipio (OpenStreetMap Nominatim), marcada como tal.
- `docs/mapa-implementacion.md` y `scripts/verificar.sh`: puertas de control por paso.

### Seguridad (auditoría D2)
- Teléfonos de autoridades no se importan por defecto (minimización).
- `Referrer-Policy` de producción: `strict-origin-when-cross-origin` (requerido por el servidor de teselas).
- Expresión de coordenadas sin retroceso cuadrático.

### Seguridad (auditoría D1, `docs/auditoria-2026-11-24.md`)
- SeaweedFS: componentes internos solo en `127.0.0.1`; solo la API S3 con credenciales en la red.
- EasyPanel: `web` y `worker` fuerzan la configuración de producción.
- Inicio de sesión fallido: sin error 500 con usuarios largos y sin guardar lo tecleado si no es un usuario existente.
- Nadie cambia sus propios roles ni se asigna cargos; alerta por cambios de rol privilegiado.
- `backup.sh`: valida nombres de destino.

### Corregido
- SeaweedFS escuchaba solo en la IP del contenedor (`-ip.bind` vacío usa `-ip`), por lo que la verificación de salud en `localhost` fallaba y `s3` quedaba *unhealthy*. Ahora escucha en `0.0.0.0` y la verificación tiene 30 s de gracia al arrancar.

### Añadido
- **Respaldo diario cifrado**: servicio `backup` (restic + rclone + pg_dump 17) con cron, retención, verificación semanal, registro en bitácora y alerta si falta respaldo; `restore.sh` con protección contra sobrescribir la base en uso. Probado localmente (respaldo y restauración idénticos) y en CI.
- **Seguridad (`apps/seguridad`)**: roles como grupos; autorización central `puede(usuario, acción, objeto)` con matriz probada rol × acción × clasificación; segundo factor TOTP obligatorio para administrador, director, auditor y superusuario, con códigos de recuperación de un solo uso; bloqueo tras 5 intentos (15 min) por usuario + IP; IP real detrás del proxy; sesión con inactividad de 30 min y máximo absoluto de 10 h; pantalla «Mis sesiones»; cabeceras CSP y Permissions-Policy; alertas por correo (superusuario, 10 fallos en 10 min, cuentas desactivadas, falta de respaldo); desactivación diaria de cuentas sin cargo; el rol administrador no puede otorgarse superusuario ni staff.
- **Bitácora (`apps/auditoria`)**: solo agregado; PostgreSQL rechaza UPDATE y DELETE mediante trigger; oculta campos sensibles; visible en el admin solo para administrador y auditor.
- **Eventos (`apps/eventos`)**: outbox transaccional, procesamiento con `SKIP LOCKED`, reintentos (máx. 5) y tareas periódicas del worker.
- Catálogos: cambios en el admin y en ocupaciones de cargo registrados en la bitácora y en eventos; permisos del admin por `puede()`.
- Página de inicio con roles, cargos vigentes y estado del segundo factor; el admin usa el mismo inicio de sesión.
- `docs/plan-general.md`: módulos M1-M10, firma en dos niveles, alcance de activos frente al registro oficial, orden del demo (D1-D6) y reglas para usar datos reales.
- Creación opcional del administrador al arrancar `web` con `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` y `DJANGO_SUPERUSER_PASSWORD` (para servidores sin acceso SSH). Si el usuario existe, continúa sin error.
- Despliegue en EasyPanel: `docker-compose.easypanel.yml` (sin puertos publicados) y guía `docs/despliegue-easypanel.md`. CI prueba ambos archivos Compose, el de EasyPanel con la configuración de producción.
- Catálogos (`apps/core`): unidades, cargos, personas, ocupaciones de cargo (titular, interino, suplente), instituciones externas, procesos, proyectos (con tipo, presupuesto y estados del módulo Institutos) y feriados.
- `cargos_vigentes(persona, fecha)`: base de la bandeja por cargo; las suplencias se activan y vencen solas por fecha.
- Un solo titular por cargo en cualquier fecha (servicio con bloqueo + restricción en la base); las ocupaciones no se borran, se cierran.
- Cálculo de días hábiles con feriados configurables (sin feriados precargados: los provee Recursos Humanos).
- `cargar_semillas`: estructura de la Secretaría según el MOF 2027 (borrador) con personas, instituciones y proyectos ficticios; plazos de proceso provisionales.
- Esqueleto del proyecto: Django 5.2 LTS, configuración por entorno (`base`, `dev`, `prod`, `test`) con `django-environ`, dependencias bloqueadas con `uv`.
- `GET /api/v1/salud/`: verifica base de datos y almacenamiento; responde 503 sin exponer detalles internos.
- Esquema OpenAPI en `/api/v1/esquema/` y documentación en `/api/v1/docs/`.
- `Dockerfile` multi-etapa con usuario no root y estáticos servidos por WhiteNoise (sin CDN).
- Comando `procesar_eventos` (sin consumidores todavía; se completan en el paso 3).
- Integración continua: ruff, import-linter, bandit, pip-audit, gitleaks, `check --deploy`, pytest con PostgreSQL + pgvector y prueba de punta a punta con Docker Compose.
- Especificación, documentos de seguridad, políticas, respaldos, levantamiento de noviembre de 2026 y módulo Institutos.
