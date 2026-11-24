#!/usr/bin/env bash
# Respaldo cifrado (restic) de la base de datos y los archivos hacia cada destino de
# BACKUP_DESTINOS. Registra el resultado en la bitácora de seguridad. Ver docs/respaldos.md.
set -Eeuo pipefail

: "${DATABASE_URL:?Falta DATABASE_URL}"
: "${BACKUP_DESTINOS:?Falta BACKUP_DESTINOS (ej. local o local,nube1)}"
RETENCION="${BACKUP_RETENCION:-7d,4w,12m}"
TRABAJO="${BACKUP_DIR_TRABAJO:-/tmp/respaldo-trabajo}"
VERSION_APP="${APP_VERSION:-desconocida}"

registrar() {  # registrar ACCION JSON
  local accion="$1" detalle="$2"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -v accion="$accion" -v detalle="$detalle" <<'SQL' >/dev/null 2>&1 || echo "Aviso: no se pudo registrar en la bitácora" >&2
INSERT INTO auditoria_bitacora (categoria, actor_nombre, accion, objeto_tipo, objeto_id, despues, creado_en)
VALUES ('seguridad', 'respaldo', :'accion', 'respaldo', '', CAST(:'detalle' AS jsonb), now());
SQL
}

valor_de() {  # valor_de PREFIJO NOMBRE -> contenido de la variable PREFIJO_NOMBRE
  local var="${1}_${2}"
  printf '%s' "${!var:-}"
}

IFS=',' read -r DIARIOS SEMANALES MENSUALES <<<"$RETENCION"

respaldar_en() {  # respaldar_en REPOSITORIO CLAVE
  local repo="$1" clave="$2"
  (
    export RESTIC_REPOSITORY="$repo" RESTIC_PASSWORD="$clave"
    { restic cat config >/dev/null 2>&1 || restic init --quiet; } &&
      restic backup --quiet --host gestion-documental --tag "app-${VERSION_APP}" "$TRABAJO" &&
      restic forget --quiet --prune --host gestion-documental \
        --keep-daily "${DIARIOS%d}" --keep-weekly "${SEMANALES%w}" --keep-monthly "${MENSUALES%m}" &&
      { [[ "$(date +%u)" != "7" ]] || restic check --read-data-subset=5%; }
  )
}

rm -rf "$TRABAJO"
mkdir -p "$TRABAJO/archivos"
trap 'rm -rf "$TRABAJO"' EXIT

inicio=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "[$inicio] Respaldo: volcado de la base de datos"
pg_dump --format=custom --no-owner --file="$TRABAJO/base.dump" "$DATABASE_URL"

if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
  echo "Respaldo: copia del almacenamiento de archivos (${S3_BUCKET})"
  export RCLONE_CONFIG_ORIGEN_TYPE=s3
  export RCLONE_CONFIG_ORIGEN_PROVIDER=SeaweedFS
  export RCLONE_CONFIG_ORIGEN_ENDPOINT="$S3_ENDPOINT_URL"
  export RCLONE_CONFIG_ORIGEN_ACCESS_KEY_ID="$S3_ACCESS_KEY"
  export RCLONE_CONFIG_ORIGEN_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
  export RCLONE_CONFIG_ORIGEN_REGION="${S3_REGION:-us-east-1}"
  rclone copy "origen:${S3_BUCKET}" "$TRABAJO/archivos" --quiet
else
  echo "Respaldo: sin almacenamiento S3 configurado; solo base de datos"
fi

fallidos=()
correctos=()
IFS=',' read -r -a DESTINOS <<<"$BACKUP_DESTINOS"
for destino in "${DESTINOS[@]}"; do
  destino="${destino// /}"
  [[ -z "$destino" ]] && continue
  repo=$(valor_de RESTIC_REPOSITORY "$destino")
  clave=$(valor_de RESTIC_PASSWORD "$destino")
  if [[ -z "$repo" || -z "$clave" ]]; then
    echo "ERROR: faltan RESTIC_REPOSITORY_${destino} o RESTIC_PASSWORD_${destino}" >&2
    fallidos+=("$destino")
    continue
  fi
  echo "Respaldo: destino '${destino}'"
  # Dentro de un "if" bash ignora "set -e": cada paso se encadena con && a propósito.
  if respaldar_en "$repo" "$clave"; then
    correctos+=("$destino")
  else
    echo "ERROR: falló el respaldo en '${destino}'" >&2
    fallidos+=("$destino")
  fi
done

tamano=$(du -sb "$TRABAJO" | cut -f1)
detalle=$(printf '{"inicio":"%s","fin":"%s","correctos":"%s","fallidos":"%s","bytes":%s}' \
  "$inicio" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${correctos[*]:-}" "${fallidos[*]:-}" "$tamano")

if ((${#fallidos[@]})) || ! ((${#correctos[@]})); then
  echo "Respaldo con errores en: ${fallidos[*]:-ningún destino válido}" >&2
  registrar respaldo_fallido "$detalle"
  exit 1
fi
registrar respaldo_ok "$detalle"
echo "Respaldo completado en: ${correctos[*]}"
