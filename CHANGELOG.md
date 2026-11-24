# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado semántico.

## [Sin publicar]

### Corregido
- SeaweedFS escuchaba solo en la IP del contenedor (`-ip.bind` vacío usa `-ip`), por lo que la verificación de salud en `localhost` fallaba y `s3` quedaba *unhealthy*. Ahora escucha en `0.0.0.0` y la verificación tiene 30 s de gracia al arrancar.

### Añadido
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
