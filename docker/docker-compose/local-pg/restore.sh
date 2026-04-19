#!/usr/bin/env bash
set -euo pipefail

umask 077

usage() {
    cat <<'EOF'
Usage:
  restore.sh [--yes] <dump-file>

Restores a PostgreSQL custom-format dump into the configured Hindsight database.
The script stops API/control-plane services temporarily, recreates the target
database, restores the dump, and starts previously running app services again.
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.yaml}"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
DB_SERVICE="${HINDSIGHT_DB_SERVICE:-db}"
APP_SERVICES="${HINDSIGHT_APP_SERVICES:-hindsight-api hindsight-cp}"
CONFIRM=false

while (($# > 0)); do
    case "$1" in
        --yes)
            CONFIRM=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if (($# != 1)); then
    usage >&2
    exit 1
fi

DUMP_FILE="$1"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.example to .env first." >&2
    exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
    echo "Dump file not found: $DUMP_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

TARGET_DB="${POSTGRES_DB:-${HINDSIGHT_DB_NAME:-hindsight_db}}"
TARGET_USER="${POSTGRES_USER:-${HINDSIGHT_DB_USER:-hindsight_user}}"

if [[ "$CONFIRM" != true ]]; then
    echo "This will replace database '$TARGET_DB' from dump '$DUMP_FILE'." >&2
    read -r -p "Continue? [y/N] " ANSWER
    case "$ANSWER" in
        y|Y|yes|YES)
            ;;
        *)
            echo "Aborted." >&2
            exit 1
            ;;
    esac
fi

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d "$DB_SERVICE" >/dev/null

RUNNING_APP_SERVICES=()
for SERVICE in $APP_SERVICES; do
    SERVICE_ID="$(
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --status running -q "$SERVICE" 2>/dev/null || true
    )"
    if [[ -n "$SERVICE_ID" ]]; then
        RUNNING_APP_SERVICES+=("$SERVICE")
    fi
done

if ((${#RUNNING_APP_SERVICES[@]} > 0)); then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop "${RUNNING_APP_SERVICES[@]}" >/dev/null
fi

restore_services() {
    if ((${#RUNNING_APP_SERVICES[@]} > 0)); then
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d "${RUNNING_APP_SERVICES[@]}" >/dev/null
    fi
}
trap restore_services EXIT

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$DB_SERVICE" sh -lc '
    export PGPASSWORD="$POSTGRES_PASSWORD"
    until pg_isready -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1; do
        sleep 1
    done
    psql -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\''$POSTGRES_DB'\'' AND pid <> pg_backend_pid();" >/dev/null
    dropdb -h 127.0.0.1 -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
    createdb -h 127.0.0.1 -U "$POSTGRES_USER" "$POSTGRES_DB"
' >/dev/null

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$DB_SERVICE" sh -lc \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_restore -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
    < "$DUMP_FILE"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T "$DB_SERVICE" sh -lc '
    export PGPASSWORD="$POSTGRES_PASSWORD"
    psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT 1;" >/dev/null
' >/dev/null

trap - EXIT
restore_services

echo "Restore completed from $DUMP_FILE into database '$TARGET_DB' as user '$TARGET_USER'."
