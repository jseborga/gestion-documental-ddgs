# Despliegue en EasyPanel

Se despliega como un servicio **Compose** con el archivo `docker-compose.easypanel.yml`: base de datos (PostgreSQL 17 + pgvector), almacenamiento (SeaweedFS), aplicación web y procesador de eventos quedan juntos, igual que en la prueba automática de CI.

> Estado actual (v0.1, pasos 1-2): solo están disponibles el panel de administración y `/api/v1/salud/`. Sirve para validar la infraestructura, **no para cargar datos reales**: todavía no hay respaldos automáticos (paso 9) y el lugar de alojamiento para datos reales lo debe aprobar la Unidad de Sistemas.

## Requisitos

- Servidor con EasyPanel instalado y un dominio (o subdominio) apuntando a su IP.
- Recursos mínimos del piloto: 4 vCPU, 8 GB de RAM, 200 GB de disco (SPEC.md §11).
- Acceso de administrador al repositorio en GitHub para agregar una *deploy key*.

## Pasos

1. **Proyecto.** En EasyPanel crear un proyecto, por ejemplo `gestion-documental`.
2. **Servicio Compose (no "App").** *New Service* → **Compose** → nombre `app`. Si se crea como *App*, EasyPanel intenta leer el Compose como Dockerfile y falla con `unknown instruction: name:`. Fuente **Git**:
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

   - `DJANGO_ALLOWED_HOSTS` lleva solo el nombre del dominio (sin `https://` ni `/`) y debe incluir `localhost`, que usa la verificación de salud interna.
   - `CSRF_TRUSTED_ORIGINS` lleva `https://` y **no** lleva puerto (`:8000` es interno).
   - PostgreSQL fija la clave en el **primer** despliegue. Cambiarla después en `.env` no la cambia en la base: hay que borrar el volumen `<proyecto>_db_data` (solo si no hay datos) o cambiarla dentro de PostgreSQL.
   - Generar claves, por ejemplo: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.
   - Si la clave de PostgreSQL tiene caracteres especiales (`@`, `:`, `/`), codificarlos en `DATABASE_URL` o usar solo letras y números.
5. **Dominio.** En *Domains*: host = su dominio, path `/`, **Compose service = `web`**, puerto destino = `8000`, protocolo interno **HTTP**, HTTPS activado. No publicar `db` ni `s3`. Si el servicio queda vacío, EasyPanel responde "servicio no encontrado".
6. **Desplegar** y revisar los registros. La primera construcción tarda varios minutos. `web` aplica las migraciones al arrancar.
7. **Comprobar:** `https://<su-dominio>/api/v1/salud/` debe responder `{"estado": "ok", ...}`.
8. **Usuario administrador.** Dos opciones:
   - **Sin SSH (desde EasyPanel):** agregar temporalmente en *Environment*:

     ```dotenv
     DJANGO_SUPERUSER_USERNAME=admin
     DJANGO_SUPERUSER_EMAIL=correo@institucion.bo
     DJANGO_SUPERUSER_PASSWORD=<clave de 12+ caracteres>
     ```

     Desplegar: `web` crea el usuario al arrancar (si ya existe, lo informa y sigue). Entrar a `/admin/` y **después borrar esas tres líneas y volver a desplegar**, para que la clave no quede guardada en el servidor.
   - **Con SSH:**

     ```bash
     docker exec -it <proyecto>_<servicio>-web-1 python manage.py createsuperuser
     ```

   Datos ficticios de prueba (opcional): `docker exec -it <proyecto>_<servicio>-web-1 python manage.py cargar_semillas`.
   No se crean usuarios desde la terminal de la base de datos: Django guarda las claves cifradas (hash) y un `INSERT` directo deja un usuario inutilizable.
9. **Actualizaciones.** Cada `git push` a `main` no se despliega solo: usar *Deploy* en EasyPanel (o configurar un disparador de despliegue) después de que CI esté en verde.

## Problemas frecuentes

| Síntoma | Causa probable |
| --- | --- |
| `Bad Request (400)` | El dominio no está en `DJANGO_ALLOWED_HOSTS` |
| Error CSRF al entrar al admin | Falta `CSRF_TRUSTED_ORIGINS=https://<su-dominio>` |
| `web` reinicia en bucle | Clave de PostgreSQL distinta entre `POSTGRES_PASSWORD` y `DATABASE_URL`; ver registros |
| Salud con `"almacenamiento": "error"` | `s3` aún iniciando o claves S3 distintas entre servicios |
| "Servicio no encontrado" | El dominio no apunta al servicio Compose `web` |
| Bad Gateway (502) | Protocolo interno en HTTPS o puerto distinto de 8000 |
| `s3` *unhealthy* | Versión anterior al 24/11/2026 sin `-ip.bind=0.0.0.0` |
| Redirecciones infinitas | El proxy no envía `X-Forwarded-Proto: https`; revisar que el dominio tenga HTTPS activado |

## Seguridad del panel

Asignar un dominio con HTTPS al propio panel de EasyPanel. Entrar por `http://IP:3000` envía sin cifrar las credenciales que controlan todo el servidor.

## Antes de usar datos reales

- Respaldo automático cifrado operativo (paso 9) y probado con una restauración.
- Versiones de imágenes fijadas (sin `latest`).
- Servidor aprobado por la Unidad de Sistemas y el Responsable de Seguridad (levantamiento A16).
- Autorización escrita del Director para cargar el registro 2026.
