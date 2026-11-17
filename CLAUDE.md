# CLAUDE.md — instrucciones para construir el prototipo

Lee `SPEC.md` completo antes de escribir código. Es la fuente de verdad; si algo falta o se contradice, pregunta en vez de inventar.

## Idioma y estilo
- Código, modelos y campos en español (como en SPEC.md); comentarios breves en español.
- Python 3.12, Django 5.2 LTS, DRF, HTMX. Formato y lint con `ruff`.
- Lógica de negocio solo en `apps/*/services.py`. Views, serializers y admin llaman a servicios; nunca cambian estados directamente.
- Cada transición: `transaction.atomic()` + registro en `Bitacora` + inserción en `EventoOutbox`, todo en la misma transacción.

## Orden de trabajo (un commit por paso, pruebas incluidas)
1. Esqueleto: `pyproject.toml`, `config/settings/{base,dev,prod}.py` con `django-environ`, `Dockerfile` multi-etapa (usuario no root), `docker-compose.yml` funcionando, `/api/v1/salud/`.
2. `apps/core`: modelos, admin, semillas sintéticas (`seeds/`), servicio `cargos_vigentes`.
3. `apps/auditoria` (con trigger append-only) y `apps/eventos` (outbox + comando `procesar_eventos --loop`).
4. `apps/archivos`: storage S3 (`django-storages`), hash SHA-256, validación de tipo/tamaño.
5. `apps/correspondencia`: modelos, secuencia CITE con bloqueo, servicios de transición, reglas de la sección 6.
6. `apps/api`: endpoints de la sección 8 + OpenAPI.
7. UI HTMX (sección 9) y `apps/tablero`.
8. `apps/importacion`: comando del Excel histórico con Excel sintético de prueba.
9. `scripts/backup.sh` y `scripts/restore.sh` con `restic`; CI en GitHub Actions.

## Comandos esperados
```
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py cargar_semillas
docker compose exec web pytest
docker compose exec web python manage.py importar_registro_excel --archivo /datos/registro.xlsx --anio 2026 --unidad DDGS --dry-run
```

## Prohibido
- Subir datos reales (Excel del registro, nombres de funcionarios, `alias.csv`, `.env`).
- Calcular el CITE con `MAX()+1` o fuera de una transacción con bloqueo.
- Usar MinIO Community (ver ADR-04); usar SeaweedFS (o Garage si SeaweedFS falla).
- Dependencias de CDN en producción.
- Microservicios, colas externas o frameworks de frontend SPA en el MVP.

## Definición de terminado
Los 7 criterios de la sección 14 de SPEC.md se cumplen y están demostrados con pruebas o con un paso documentado en README.
