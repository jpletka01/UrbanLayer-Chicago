#!/usr/bin/env bash
# SQLite backup script for UrbanLayer production server.
# Copies the WAL-mode database safely using sqlite3 .backup command.
# Keeps the most recent N backups (default 7).
#
# Usage: ./scripts/backup_db.sh [backup_dir] [keep_count]
# Cron:  0 3 * * * /opt/urbanlayer/scripts/backup_db.sh /opt/urbanlayer/backups 7

set -euo pipefail

DB_PATH="${1:-/opt/urbanlayer/backend/data/urbanlayer.db}"
BACKUP_DIR="${2:-/opt/urbanlayer/backups}"
KEEP="${3:-7}"

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
