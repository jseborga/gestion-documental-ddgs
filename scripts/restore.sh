#!/usr/bin/env bash
# Restaura un respaldo de restic: base de datos y, opcionalmente, archivos.
# Uso: restore.sh DESTINO [SNAPSHOT]   (SNAPSHOT por defecto: latest)
# Destino de la base: RESTORE_DATABASE_URL. Restaurar sobre DATABASE_URL exige
# RESTAURAR_SOBRE_PRODUCCION=si. Archivos: RESTAURAR_ARCHIVOS=si (al bucket S3 configurado).
set -Eeuo pipefail

destino="${1:?Uso: restore.sh DESTINO [SNAPSHOT]}"
snapshot="${2:-latest}"
repo_var="RESTIC_REPOSITORY_${destino}"
clave_var="RESTIC_PASSWORD_${destino}"
export RESTIC_REPOSITORY="${!repo_var:?Falta ${repo_var}}"
export RESTIC_PASSWORD="${!clave_var:?Falta ${clave_var}}"
objetivo="${RESTORE_DATABASE_URL:-}"

if [[ -z "$objetivo" ]]; then
  echo "Defina RESTORE_DATABASE_URL (base donde restaurar)." >&2
  exit 2
fi
if [[ "$objetivo" == "${DATABASE_URL:-}" && "${RESTAURAR_SOBRE_PRODUCCION:-no}" != "si" ]]; then
  echo "RESTORE_DATABASE_URL es la base en uso. Para sobrescribirla: RESTAURAR_SOBRE_PRODUCCION=si" >&2
  exit 2
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "Restaurando snapshot '${snapshot}' de '${destino}'"
restic restore "$snapshot" --host gestion-documental --target "$tmp" --quiet
dump=$(find "$tmp" -name base.dump -type f | head -n1)
[[ -f "$dump" ]] || { echo "El snapshot no contiene base.dump" >&2; exit 1; }

pg_restore --clean --if-exists --no-owner --exit-on-error --dbname="$objetivo" "$dump"
echo "Base de datos restaurada."

if [[ "${RESTAURAR_ARCHIVOS:-no}" == "si" ]]; then
  S3_ENDPOINT="${S3_ENDPOINT:-${S3_ENDPOINT_URL:-}}"
  : "${S3_ENDPOINT:?Falta S3_ENDPOINT}" "${S3_BUCKET:?Falta S3_BUCKET}"
  export RCLONE_CONFIG_DESTINO_TYPE=s3
  export RCLONE_CONFIG_DESTINO_PROVIDER=SeaweedFS
  export RCLONE_CONFIG_DESTINO_ENDPOINT="$S3_ENDPOINT"
  export RCLONE_CONFIG_DESTINO_ACCESS_KEY_ID="$S3_ACCESS_KEY"
  export RCLONE_CONFIG_DESTINO_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
  export RCLONE_CONFIG_DESTINO_REGION="${S3_REGION:-us-east-1}"
  carpeta=$(dirname "$dump")/archivos
  rclone copy "$carpeta" "destino:${S3_BUCKET}" --quiet
  echo "Archivos restaurados en el bucket ${S3_BUCKET}."
fi

# Prueba de humo: la restauración tiene las tablas base del sistema.
psql "$objetivo" -v ON_ERROR_STOP=1 -Atc "SELECT count(*) FROM django_migrations" >/dev/null
echo "Restauración verificada."
