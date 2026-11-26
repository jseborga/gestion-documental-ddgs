# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado semántico.

## [Sin publicar]

### Añadido
- Pantalla «Importar planillas» de institutos (solo administrador, con segundo factor): subida desde el celular o la PC, simulación previa, mismas defensas del comando, archivos temporales borrados al terminar.
- Botón «Ubicar de forma aproximada»: la consulta a OpenStreetMap corre en el proceso de fondo (worker) y su resultado queda en la bitácora.
- `cargar_semillas --solo-estructura`: carga unidades, cargos y procesos sin personas, institutos ni proyectos ficticios (para demos con datos reales).

### Cambiado (almacenamiento, 26/11/2026)
- El Compose de EasyPanel mantiene su SeaweedFS propio (`S3_ENDPOINT=http://s3:8333`). Variables: `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` (se acepta `S3_ENDPOINT_URL` por compatibilidad). `s3-init` se reemplaza por `preparar_almacenamiento`.
- Perfil opcional `seaweedfs-externo` con `s3-proxy` (socat, sin privilegios) para usar un SeaweedFS privado ya existente: boto3 rechaza los nombres internos con guion bajo de EasyPanel. La app no arranca, con mensaje claro, si `S3_ENDPOINT` tiene guion bajo.
- `preparar_almacenamiento` al arrancar: comprueba o crea el bucket.
- Los almacenamientos bloquean `url()`: los archivos nunca exponen la URL interna; se descargarán por el backend con verificación de permisos.

### Corregido
- SeaweedFS vuelve a `-ip.bind=0.0.0.0`: el aislamiento en `127.0.0.1` impedía que el servicio pasara su verificación de salud en EasyPanel. El hallazgo 1 de la auditoría D1 queda reabierto (ver `docs/auditoria-2026-11-24.md`).
- La imagen Docker no se construía: `leaflet.js` referencia `leaflet.js.map` y el almacenamiento de estáticos de producción lo exige. Se incluye el archivo del mismo paquete npm (sumas SHA-256 actualizadas) y la generación de estáticos de producción pasa a la puerta de control y a la CI.

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
