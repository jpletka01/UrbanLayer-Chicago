#!/usr/bin/env bash
# SQLite backup for the UrbanLayer production server.
# Copies the WAL-mode database safely with sqlite3's .backup command and keeps
# the most recent N copies (default 7).
#
# Usage: ./scripts/backup_db.sh [db_path] [backup_dir] [keep_count]
# Cron:  0 3 * * * /opt/urbanlayer/scripts/backup_db.sh
#
# The app database is chicago.db in the backend_data Docker volume. (The old
# default, backend/data/urbanlayer.db, never existed, so earlier cron runs
# exited without making a backup.) These copies stay on the same host; see
# deploy/hardening-runbook.md for shipping them off-box.

set -euo pipefail

DB_PATH="${1:-/var/lib/docker/volumes/urbanlayer_backend_data/_data/chicago.db}"
BACKUP_DIR="${2:-/opt/urbanlayer/backups}"
KEEP="${3:-7}"

command -v sqlite3 >/dev/null || { echo "sqlite3 is not installed (apt install sqlite3)" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/urbanlayer_${TIMESTAMP}.db"

if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
echo "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Prune old backups, keep the most recent $KEEP
ls -1t "$BACKUP_DIR"/urbanlayer_*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "Retained $(ls -1 "$BACKUP_DIR"/urbanlayer_*.db 2>/dev/null | wc -l) backups"
