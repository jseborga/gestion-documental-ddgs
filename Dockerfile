# syntax=docker/dockerfile:1
# Etapa 1: dependencias con uv a partir del archivo de bloqueo.
FROM python:3.12-slim AS dependencias
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Etapa 2: imagen de ejecución, sin herramientas de compilación y con usuario no root.
FROM python:3.12-slim AS ejecucion
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=dependencias /opt/venv /opt/venv
COPY --chown=app:app . .
# collectstatic en la construcción: valores ficticios solo para este paso.
RUN DJANGO_SECRET_KEY=solo-construccion DATABASE_URL=sqlite:////tmp/x.db \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
