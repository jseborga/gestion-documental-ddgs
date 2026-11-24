#!/bin/sh
# Programa el respaldo diario con el cron de busybox y queda en primer plano.
set -eu
HORARIO="${BACKUP_HORARIO:-0 2 * * *}"
echo "${HORARIO} /usr/local/bin/backup.sh > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/crontabs/root
echo "Respaldo programado: ${HORARIO} (zona ${TZ:-UTC}). Destinos: ${BACKUP_DESTINOS:-sin definir}"
exec crond -f -l 6
