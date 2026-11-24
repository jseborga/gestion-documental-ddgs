# Respaldos con varios proveedores

Versión 0.1 · 16/11/2026

## 1. Objetivos
| Indicador | Meta inicial |
| --- | --- |
| RPO (datos que se pueden perder como máximo) | 24 h (copia diaria); 1 h si se activa archivado continuo de PostgreSQL (fase posterior) |
| RTO (tiempo máximo para volver a operar) | 4 h |
| Regla | **3-2-1**: 3 copias, en 2 tipos de medio, 1 fuera del edificio |

## 2. Qué se respalda
1. Base de datos: `pg_dump` en formato *custom* (incluye vectores de pgvector).
2. Archivos: exportación del bucket S3 (documentos y adjuntos).
3. Configuración no secreta: `docker-compose.yml`, versión de la imagen, `CHANGELOG.md`.
4. **No** se respaldan secretos en el mismo repositorio de respaldo: `.env` y las claves se custodian aparte (ver §6).

## 3. Herramienta: restic (+ rclone)
- **restic** cifra en el servidor antes de enviar, deduplica y guarda versiones (*snapshots*). El proveedor de nube nunca ve el contenido.
- Destinos nativos de restic: disco local o NAS, SFTP, servidor REST, Amazon S3 y compatibles, Backblaze B2, Microsoft Azure Blob Storage, Google Cloud Storage.
- Destinos vía **rclone** (más de 70 servicios): Dropbox, Microsoft OneDrive, Google Drive, y otros.

## 4. Destinos recomendados (en orden)
| Prioridad | Destino | Uso | Comentario |
| --- | --- | --- | --- |
| 1 | Disco/NAS en otra sala de la Gobernación | Copia local rápida | Restauración en minutos |
| 2 | Almacenamiento de objetos en nube: AWS S3, Google Cloud Storage, Azure Blob o Backblaze B2 | Copia fuera del edificio | Activar **bloqueo de objetos / inmutabilidad** del proveedor para resistir ransomware y borrados |
| 3 (opcional) | Dropbox, OneDrive o Google Drive vía rclone | Tercera copia económica | No usar como única copia externa: estos servicios limitan la velocidad agresivamente y las tareas de mantenimiento del repositorio pueden ser lentas |

Se pueden configurar **varios destinos a la vez**: el script recorre la lista y respalda en cada uno; si uno falla, continúa con los demás y alerta.

Antes de usar una nube extranjera: confirmación de Asesoría Legal y Administración (ver nota de AWS/región y ausencia de norma de residencia en el diagnóstico). Al ir cifrado en origen, el riesgo de confidencialidad es bajo, pero la decisión es institucional.

## 5. Implementación
- Contenedor `backup` (perfil `backup` en `docker-compose.yml`) construido desde `docker/backup/Dockerfile`: Alpine + `restic` + `rclone` + `postgresql-client` + cliente S3.
- `scripts/backup.sh`:
  1. `pg_dump` a un archivo temporal.
  2. Copia del bucket a un directorio temporal (o lectura directa).
  3. Para cada destino de `BACKUP_DESTINOS`: `restic backup` con etiquetas (`db`, `archivos`, versión de la app).
  4. `restic forget --prune` según retención (7 diarios, 4 semanales, 12 mensuales; configurable). En destinos con inmutabilidad, el borrado respeta el periodo de bloqueo.
  5. `restic check --read-data-subset=5%` semanal.
  6. Registro del resultado en la bitácora de seguridad y alerta por correo si falla.
- `scripts/restore.sh DESTINO SNAPSHOT`: restaura base y archivos en un entorno limpio, verifica hashes de adjuntos contra la base y ejecuta la prueba de humo.
- Programación: diaria a las 02:00 (cron del servidor o servicio `ofelia`/`supercronic` en el contenedor).

## 6. Custodia de claves
- Cada destino tiene su propia contraseña de restic (`RESTIC_PASSWORD_n`). Sin ella **los respaldos son irrecuperables**.
- Las contraseñas y credenciales de nube se entregan a la Gobernación en sobre cerrado o gestor de contraseñas institucional, con acta, y se custodian fuera del servidor. El proveedor de mantenimiento no debe ser el único que las conoce.
- Las credenciales de nube usan cuentas o llaves **solo de escritura/lectura del bucket de respaldo**, nunca cuentas de administrador del proveedor.

## 7. Pruebas obligatorias
| Frecuencia | Prueba | Evidencia |
| --- | --- | --- |
| Mensual (automática) | Restaurar el último snapshot de un destino rotativo en un contenedor temporal y correr la prueba de humo | Registro en bitácora + informe |
| Trimestral (manual) | Restauración completa en servidor limpio midiendo el RTO | Acta firmada |
| Cada versión mayor | Restaurar un respaldo hecho con la versión anterior | Nota en CHANGELOG |

## 8. Variables de entorno (ver `.env.example`)
```
BACKUP_DESTINOS=local,nube1           # nombres separados por coma
BACKUP_RETENCION=7d,4w,12m
RESTIC_REPOSITORY_local=/respaldos/restic
RESTIC_PASSWORD_local=...
RESTIC_REPOSITORY_nube1=s3:https://s3.amazonaws.com/mi-bucket-respaldo   # AWS S3
# RESTIC_REPOSITORY_nube1=gs:mi-bucket-respaldo:/gestion                  # Google Cloud Storage
# RESTIC_REPOSITORY_nube1=azure:mi-contenedor:/gestion                    # Azure Blob
# RESTIC_REPOSITORY_nube1=b2:mi-bucket:/gestion                           # Backblaze B2
# RESTIC_REPOSITORY_nube1=rclone:dropbox:respaldos/gestion                # Dropbox vía rclone
# RESTIC_REPOSITORY_nube1=rclone:onedrive:respaldos/gestion               # OneDrive vía rclone
RESTIC_PASSWORD_nube1=...
```
Las credenciales de cada proveedor (AWS, Google, Azure, B2, rclone) van en variables o archivos montados como secretos, nunca en el repositorio. La sintaxis exacta de cada destino se verifica contra la documentación de restic al implementar.

## 9. Estado de implementación (24/11/2026, etapa D1)

- Servicio `backup` activo en `docker-compose.easypanel.yml` (en el Compose de desarrollo, perfil `backup`). Programa `backup.sh` con el cron del contenedor (`BACKUP_HORARIO`, por defecto 02:00, zona `TZ`).
- Respalda la base (`pg_dump` formato custom) y el bucket S3 (`rclone`), cifrados por restic, en cada destino de `BACKUP_DESTINOS`; aplica la retención y verifica el 5 % de los datos los domingos.
- Registra `respaldo_ok` o `respaldo_fallido` en la bitácora de seguridad. El worker alerta por correo si no hay un respaldo exitoso en `RESPALDO_ALERTA_HORAS` (26 h).
- `restore.sh DESTINO [SNAPSHOT]` restaura en `RESTORE_DATABASE_URL`; se niega a sobrescribir la base en uso salvo `RESTAURAR_SOBRE_PRODUCCION=si`. La CI respalda y restaura en una base nueva en cada cambio.
- **Limitación actual:** con solo el destino `local`, la copia queda en el mismo servidor. Protege contra errores y borrados, no contra la pérdida del servidor. Antes de producción se agrega al menos un destino fuera del servidor (SFTP a otro equipo en Bolivia o nube autorizada, ver §4).

Manual:

```bash
docker exec -it <proyecto>_<servicio>-backup-1 backup.sh
docker exec -it -e RESTORE_DATABASE_URL=postgres://gestion:CLAVE@db:5432/restaurada <proyecto>_<servicio>-backup-1 restore.sh local
```
