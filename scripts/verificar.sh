#!/usr/bin/env bash
# Puerta de control local (docs/mapa-implementacion.md §1, P2-P8). Lo mismo que la CI.
# Requiere uv y DATABASE_URL apuntando a un PostgreSQL de pruebas.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-clave-solo-para-verificar}"
: "${DATABASE_URL:?Defina DATABASE_URL (PostgreSQL de pruebas)}"

paso() { printf '\n== %s\n' "$1"; }

paso "P8 Sin archivos de datos reales en el repositorio"
if git ls-files | grep -Ei '\.(xlsx|xlsm|xls|csv|dump|sql\.gz)$' | grep -v '^tests/fixtures/'; then
  echo "ERROR: hay archivos de datos versionados (arriba)." >&2
  exit 1
fi
echo "ok"

paso "P3 Formato y lint"
uv run ruff format --check .
uv run ruff check .

paso "P3 Análisis estático de seguridad"
uv run bandit -q -c pyproject.toml -r apps config

paso "P5 Límites entre módulos"
uv run lint-imports

paso "P6 Migraciones completas"
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test

paso "P7 Configuración de producción"
DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  DJANGO_ALLOWED_HOSTS=ejemplo.bo \
  uv run python manage.py check --deploy --fail-level WARNING --settings=config.settings.prod

paso "P7 Estáticos de producción (igual que el Dockerfile)"
# El almacenamiento con manifiesto sigue referencias de CSS/JS (p. ej. sourceMappingURL):
# si falta un archivo, la imagen Docker no se construye.
rm -rf staticfiles
env -i PATH="$PATH" HOME="$HOME" DJANGO_SETTINGS_MODULE=config.settings.prod \
  DJANGO_SECRET_KEY=solo-construccion DATABASE_URL=sqlite:////tmp/verificar-estaticos.db \
  uv run python manage.py collectstatic --noinput -v0
rm -rf staticfiles
echo "ok"

paso "P2 Pruebas y cobertura"
uv run pytest -q -p no:logging --cov=apps --cov-report=term:skip-covered --cov-fail-under=85

paso "P4 Vulnerabilidades en dependencias"
uv run pip-audit --strict --skip-editable

printf '\nPuerta superada.\n'
