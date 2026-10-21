#!/usr/bin/env bash
# SQLite backup for the UrbanLayer production server.
# Copies the WAL-mode database safely with sqlite3's .backup command and keeps
# the most recent N copies (default 7).
#
# Usage: ./scripts/backup_db.sh [db_path] [backup_dir] [keep_count]
# Cron:  0 3 * * * /opt/urbanlayer/scripts/backup_db.sh >> /var/log/urbanlayer-backup.log 2>&1
#
# The app database is chicago.db in the backend_data Docker volume, which is
# now the default. (The old default, backend/data/urbanlayer.db, doesn't exist;
# production's cron entry passed the right path, so backups did run.)
#
# Copies hold user data, so they are not world-readable: the backup dir is
# root:jack with setgid (2750), and the umask below makes each copy 640, so
# jack can read them (scripts/pull_backups.sh pulls them off-box) and nobody
# else can. See deploy/hardening-runbook.md section 8c.

set -euo pipefail
umask 027

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

# Tell the data-health checker (WS6 M2). It runs in a container that cannot see $BACKUP_DIR, so
# the report goes beside the database, on the backend_data volume it does mount. Written last and
# atomically (temp + rename): the file existing at all means a backup just completed, and its age
# is how a stopped cron job is noticed (backup_db.sh stopped silently after 2026-09-28).
STATUS_FILE="$(dirname "$DB_PATH")/backup_status.json"
RETAINED=$(ls -1 "$BACKUP_DIR"/urbanlayer_*.db 2>/dev/null | wc -l | tr -d ' ')
SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
printf '{"completed_at": "%s", "newest_backup": "%s", "size_bytes": %s, "retained": %s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$(basename "$BACKUP_FILE")" "$SIZE" "$RETAINED" > "$STATUS_FILE.tmp"
chmod 644 "$STATUS_FILE.tmp"
mv "$STATUS_FILE.tmp" "$STATUS_FILE"
