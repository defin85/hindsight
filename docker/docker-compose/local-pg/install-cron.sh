#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run this script with sudo." >&2
    exit 1
fi

if ! command -v crond >/dev/null 2>&1; then
    echo "crond is not installed. Install the cronie package first." >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"

RUN_AS_USER="${RUN_AS_USER:-${SUDO_USER:-$USER}}"
RUN_AS_HOME="$(getent passwd "$RUN_AS_USER" | cut -d: -f6)"
if [[ -z "$RUN_AS_HOME" ]]; then
    echo "Could not determine home directory for user '$RUN_AS_USER'." >&2
    exit 1
fi

STATE_DIR="${HINDSIGHT_STATE_DIR:-$RUN_AS_HOME/.local/state/hindsight}"
LOG_FILE="${HINDSIGHT_BACKUP_LOG:-$STATE_DIR/backup-cron.log}"
CRON_FILE="${HINDSIGHT_CRON_FILE:-/etc/cron.d/hindsight-local-backup}"
SCHEDULE="${HINDSIGHT_BACKUP_SCHEDULE:-0 22 * * *}"

install -d -m 700 -o "$RUN_AS_USER" -g "$RUN_AS_USER" "$STATE_DIR"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/sbin:/sbin:/bin
MAILTO=""
$SCHEDULE $RUN_AS_USER cd $REPO_ROOT && $BACKUP_SCRIPT >> $LOG_FILE 2>&1
EOF

chmod 644 "$CRON_FILE"

echo "Installed cron job in $CRON_FILE"
echo "Schedule: $SCHEDULE"
echo "Run as user: $RUN_AS_USER"
echo "Log file: $LOG_FILE"
