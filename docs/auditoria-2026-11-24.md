# Auditoría de seguridad: etapa D1

Fecha: 24/11/2026 · Alcance: `apps/seguridad`, `apps/auditoria`, `apps/eventos`, `apps/core`, `config/settings`, `scripts/backup.sh`, `scripts/restore.sh`, `Dockerfile`, `docker/backup`, `docker-compose*.yml`. Revisión de código asistida por herramientas; **no reemplaza la prueba de penetración externa** exigida antes de producción (docs/seguridad.md §3).

## Herramientas

| Herramienta | Resultado |
| --- | --- |
| `pip-audit --strict` | Sin vulnerabilidades conocidas en dependencias |
| `bandit` | Sin hallazgos |
| `ruff` (reglas `S`) | Sin hallazgos |
| Búsqueda de secretos en el historial de git | Solo valores de ejemplo (`.env.example`, pruebas) |
| `manage.py check --deploy` (producción) | Sin advertencias (se silencia solo `W021`, precarga HSTS, decisión deliberada) |
| `import-linter` | 2 contratos cumplidos |
| `shellcheck` | Sin hallazgos en los scripts de respaldo |
| Pruebas | 108 pruebas; cobertura 94 % en `apps/` |
| `gitleaks`, `trivy` | No disponibles en este entorno; corren en la CI de GitHub (gitleaks) o quedan pendientes (trivy) |

## Hallazgos y estado

| # | Severidad | Hallazgo | Estado |
| --- | --- | --- | --- |
| 1 | **Alta** | SeaweedFS exponía sus componentes internos (master 9333, volumen 8080, filer 8888) **sin autenticación** a toda la red de Docker. En EasyPanel esa red puede ser compartida con otros proyectos del servidor, que podrían leer los documentos sin pasar por la API S3. | **Corregido**: los componentes internos escuchan solo en `127.0.0.1`; únicamente la API S3, que exige credenciales, escucha en la red (`-s3.ip.bind=0.0.0.0`). Validado contra el código fuente de SeaweedFS; la verificación de punta a punta la hace la CI. |
| 2 | **Alta** | El Compose de EasyPanel tomaba `DJANGO_SETTINGS_MODULE` del `.env`. Con el `.env.example` copiado sin cambios corría en modo desarrollo (`DEBUG=True`): páginas de error con detalles internos y cookies sin `Secure`. | **Corregido**: `web` y `worker` fuerzan `config.settings.prod` en el Compose, sea cual sea el `.env`. |
| 3 | **Alta** (disponibilidad) | Un nombre de usuario de más de 40 caracteres en el formulario de inicio de sesión provocaba un error 500 al registrar el fallo. | **Corregido** y con prueba de regresión. |
| 4 | Media | La bitácora guardaba el texto tecleado como usuario en los intentos fallidos; a menudo es una contraseña escrita en el campo equivocado. | **Corregido**: se guarda el id solo si el usuario existe; si no, `desconocido`. |
| 5 | Media | Un usuario con rol administrador podía darse a sí mismo el rol director y asignarse el cargo de Director, y así firmar. | **Corregido**: nadie cambia sus propios roles ni se asigna cargos (salvo el superusuario de emergencia); todo cambio a un rol privilegiado envía alerta por correo. |
| 6 | Media | `backup.sh` terminaba sin registrar nada si un nombre de destino tenía caracteres no válidos. | **Corregido**: se valida el nombre y se registra `respaldo_fallido`. |
| 7 | Media | Error de lógica en `backup.sh`: `set -e` no rige dentro de una condición `if`, por lo que una falla de restic se habría informado como éxito. | **Corregido antes de publicar**, con pasos encadenados con `&&`; probado con un destino fallido. |
| 8 | Media (riesgo residual) | El bloqueo es por usuario + IP (para que nadie bloquee a otro a propósito). Un atacante con muchas IP podría probar 5 claves por IP. | **Mitigado**: alerta con 10 fallos en 10 min y segundo factor obligatorio para roles privilegiados. **Recomendación para el demo con datos reales**: `MFA_OBLIGATORIO_TODOS=True`. |
| 9 | Media (proceso) | La primera vez que un usuario privilegiado entra, configura su segundo factor solo con la contraseña. Si alguien conoce la contraseña antes que el titular, puede registrar su propio celular. | **Pendiente (procedimiento)**: el administrador entrega la cuenta en persona y el titular activa el segundo factor en ese momento; contraseña inicial de un solo uso. |
| 10 | Baja | La CSP permite estilos en línea (`style-src 'unsafe-inline'`) porque el admin de Django usa atributos `style`. Los scripts siguen sin `unsafe-inline`. | Aceptado y documentado. |
| 11 | Baja | La identidad S3 de la aplicación tiene la acción `Admin` (necesaria para crear el bucket). | Pendiente: separar una identidad de solo lectura y escritura para la app. |
| 12 | Baja | El contenedor de respaldo corre como root, y la URL de la base (con su clave) es visible para los procesos de ese contenedor. | Aceptado para el demo; en producción, archivo `.pgpass` montado como secreto. |
| 13 | Baja | Con un solo destino `local`, el respaldo está en el mismo servidor. | Pendiente antes de producción: destino fuera del servidor (docs/respaldos.md §9). |
| 14 | Informativo | `/api/v1/salud/` muestra la versión de la aplicación. | Aceptado (sin datos sensibles). |
| 15 | Informativo | Sin servidor de correo configurado (`EMAIL_URL=consolemail://`) las alertas solo quedan en los registros del contenedor. | **Configurar SMTP** antes de cargar datos reales. |

## Vacíos de esta revisión

- No se ejecutó SeaweedFS ni Docker en este entorno: la configuración de los contenedores se valida en la CI de GitHub.
- No se revisó el servidor de EasyPanel (sistema operativo, firewall, acceso SSH, cifrado de disco ni el propio panel).
- No hubo prueba de penetración ni revisión del PISI de la Gobernación (no fue entregado).
