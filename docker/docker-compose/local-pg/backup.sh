#!/usr/bin/env bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.yaml}"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
DB_SERVICE="${HINDSIGHT_DB_SERVICE:-db}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.example to .env first." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

BACKUP_DIR="${HINDSIGHT_BACKUP_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/hindsight/backups}"
BACKUP_KEEP="${HINDSIGHT_BACKUP_KEEP:-5}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_FILE="$BACKUP_DIR/hindsight-$TIMESTAMP.dump"
OUTPUT_FILE="${1:-$DEFAULT_FILE}"

if [[ ! "$BACKUP_KEEP" =~ ^[0-9]+$ ]]; then
    echo "HINDSIGHT_BACKUP_KEEP must be a non-negative integer." >&2
    exit 1
fi

mkdir -p "$(dirname -- "$OUTPUT_FILE")"

DB_CONTAINER_ID="$(
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --status running -q "$DB_SERVICE"
)"
if [[ -z "$DB_CONTAINER_ID" ]]; then
    echo "Database service '$DB_SERVICE' is not running." >&2
    exit 1
fi

TMP_FILE="$(mktemp "${OUTPUT_FILE}.tmp.XXXXXX")"
cleanup() {
    if [[ -f "$TMP_FILE" ]]; then
        rm -f "$TMP_FILE"
    fi
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$DB_SERVICE" sh -lc \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
    > "$TMP_FILE"

if [[ ! -s "$TMP_FILE" ]]; then
    echo "Backup failed: pg_dump produced an empty file." >&2
    exit 1
fi

mv "$TMP_FILE" "$OUTPUT_FILE"
trap - EXIT

if (( BACKUP_KEEP > 0 )); then
    mapfile -t EXISTING_BACKUPS < <(
        find "$(dirname -- "$OUTPUT_FILE")" -maxdepth 1 -type f -name 'hindsight-*.dump' -printf '%f\n' | sort -r
    )
    if (( ${#EXISTING_BACKUPS[@]} > BACKUP_KEEP )); then
        for OLD_BACKUP in "${EXISTING_BACKUPS[@]:BACKUP_KEEP}"; do
            rm -f -- "$(dirname -- "$OUTPUT_FILE")/$OLD_BACKUP"
        done
    fi
fi

echo "Backup written to $OUTPUT_FILE"
