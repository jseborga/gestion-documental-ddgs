# Despliegue en EasyPanel

Se despliega como un servicio **Compose** con el archivo `docker-compose.easypanel.yml`: base de datos (PostgreSQL 17 + pgvector), almacenamiento (SeaweedFS), aplicación web y procesador de eventos quedan juntos, igual que en la prueba automática de CI.

> Estado actual (v0.1, pasos 1-2): solo están disponibles el panel de administración y `/api/v1/salud/`. Sirve para validar la infraestructura, **no para cargar datos reales**: todavía no hay respaldos automáticos (paso 9) y el lugar de alojamiento para datos reales lo debe aprobar la Unidad de Sistemas.

## Requisitos

- Servidor con EasyPanel instalado y un dominio (o subdominio) apuntando a su IP.
- Recursos mínimos del piloto: 4 vCPU, 8 GB de RAM, 200 GB de disco (SPEC.md §11).
- Acceso de administrador al repositorio en GitHub para agregar una *deploy key*.

## Pasos

1. **Proyecto.** En EasyPanel crear un proyecto, por ejemplo `gestion-documental`.
2. **Servicio Compose.** *New Service* → **Compose** → nombre `app`. Fuente **Git**:
   - Repository URL: `git@github.com:jseborga/gestion-documental-ddgs.git`
   - Branch: `main`
   - Build Path: `/`
   - Docker Compose File: `docker-compose.easypanel.yml`
3. **Deploy key.** EasyPanel muestra una clave pública para el servicio. En GitHub: *Settings → Deploy keys → Add deploy key*, pegarla y dejar **sin** permiso de escritura.
4. **Variables de entorno.** En *Environment* activar **Create .env file**. EasyPanel copia `.env.example`; cambiar como mínimo:

   ```dotenv
   DJANGO_SETTINGS_MODULE=config.settings.prod
   DJANGO_DEBUG=False
   DJANGO_SECRET_KEY=<cadena aleatoria de 50+ caracteres>
   DJANGO_ALLOWED_HOSTS=<su-dominio>,localhost
   CSRF_TRUSTED_ORIGINS=https://<su-dominio>
   POSTGRES_PASSWORD=<clave fuerte>
   DATABASE_URL=postgres://gestion:<la misma clave>@db:5432/gestion_documental
   S3_ACCESS_KEY=<clave aleatoria>
   S3_SECRET_KEY=<clave aleatoria larga>
   INSTITUCION_NOMBRE=<nombre de la institución>
   INSTITUCION_SIGLA=<sigla>
   ```

   - `localhost` debe quedar en `DJANGO_ALLOWED_HOSTS`: lo usa la verificación de salud interna del contenedor.
   - Generar claves, por ejemplo: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.
   - Si la clave de PostgreSQL tiene caracteres especiales (`@`, `:`, `/`), codificarlos en `DATABASE_URL` o usar solo letras y números.
5. **Dominio.** En *Domains*: host = su dominio, servicio Compose = `web`, puerto destino = `8000`, HTTPS activado. No publicar `db` ni `s3`.
6. **Desplegar** y revisar los registros. La primera construcción tarda varios minutos. `web` aplica las migraciones al arrancar.
7. **Comprobar:** `https://<su-dominio>/api/v1/salud/` debe responder `{"estado": "ok", ...}`.
8. **Usuario administrador.** Por SSH en el servidor:

   ```bash
   docker ps --filter "name=web" --format "{{.Names}}"
   docker exec -it <nombre-del-contenedor-web> python manage.py createsuperuser
   docker exec -it <nombre-del-contenedor-web> python manage.py cargar_semillas   # opcional: datos ficticios
   ```

   Entrar en `https://<su-dominio>/admin/`.
9. **Actualizaciones.** Cada `git push` a `main` no se despliega solo: usar *Deploy* en EasyPanel (o configurar un disparador de despliegue) después de que CI esté en verde.

## Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| `Bad Request (400)` | El dominio no está en `DJANGO_ALLOWED_HOSTS` |
| Error CSRF al entrar al admin | Falta `CSRF_TRUSTED_ORIGINS=https://<su-dominio>` |
| `web` reinicia en bucle | Clave de PostgreSQL distinta entre `POSTGRES_PASSWORD` y `DATABASE_URL`; ver registros |
| Salud con `"almacenamiento": "error"` | `s3` aún iniciando o claves S3 distintas entre servicios |
| Redirecciones infinitas | El proxy no envía `X-Forwarded-Proto: https`; revisar que el dominio tenga HTTPS activado |

## Antes de usar datos reales

- Respaldo automático cifrado operativo (paso 9) y probado con una restauración.
- Versiones de imágenes fijadas (sin `latest`).
- Servidor aprobado por la Unidad de Sistemas y el Responsable de Seguridad (levantamiento A16).
- Autorización escrita del Director para cargar el registro 2026.
