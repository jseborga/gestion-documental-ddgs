# Gestión Documental y Correspondencia — piloto DDGS

Prototipo de sistema de correspondencia para la Dirección de Desarrollo y Gestión Social del Gobierno Autónomo Departamental de La Paz, diseñado para extenderse luego a toda la Gobernación.

- **Qué construir:** [`SPEC.md`](SPEC.md)
- **Cómo construirlo (instrucciones para Claude Code):** [`CLAUDE.md`](CLAUDE.md)
- **Seguridad:** [`docs/seguridad.md`](docs/seguridad.md) · [`SECURITY.md`](SECURITY.md)
- **Políticas de ingeniería:** [`docs/politicas-ingenieria.md`](docs/politicas-ingenieria.md)
- **Respaldos multi-proveedor:** [`docs/respaldos.md`](docs/respaldos.md)
- **Levantamiento y ajustes al MVP:** [`docs/levantamiento-2026-11.md`](docs/levantamiento-2026-11.md) · **Módulo Institutos:** [`docs/modulo-institutos.md`](docs/modulo-institutos.md)

## Arranque rápido

```bash
cp .env.example .env      # y cambiar todas las claves
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py cargar_semillas   # disponible desde el paso 2
```

Comprobación: `curl http://localhost:8000/api/v1/salud/` debe responder `{"estado": "ok", ...}`.

## Desarrollo sin Docker

Requiere Python 3.12, [uv](https://docs.astral.sh/uv/) y un PostgreSQL accesible.

```bash
uv sync
export DATABASE_URL=postgres://gestion:gestion@localhost:5432/gestion_documental
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run lint-imports
```

La integración continua (`.github/workflows/ci.yml`) ejecuta además bandit, pip-audit, gitleaks, `check --deploy` y una prueba de punta a punta con Docker Compose.

- Aplicación: http://localhost:8000
- API y documentación: http://localhost:8000/api/v1/docs/
- Correo de prueba (perfil dev): `docker compose --profile dev up -d mailpit` → http://localhost:8025

## Stack

Django 5.2 LTS · Django REST Framework · HTMX · PostgreSQL 17 + pgvector · SeaweedFS (S3) · Docker Compose.

## Datos

Este repositorio solo contiene datos **sintéticos**. El registro real (Excel), los alias de nombres y el archivo `.env` se mantienen fuera del repositorio.
