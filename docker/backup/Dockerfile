# Imagen del servicio de respaldo: restic + rclone + cliente de PostgreSQL 17.
# Se construye con el contexto en la raíz del repositorio (para copiar scripts/).
FROM alpine:3.22
RUN apk add --no-cache bash restic rclone postgresql17-client openssh-client tzdata ca-certificates
COPY scripts/backup.sh /usr/local/bin/backup.sh
COPY scripts/restore.sh /usr/local/bin/restore.sh
COPY docker/backup/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
