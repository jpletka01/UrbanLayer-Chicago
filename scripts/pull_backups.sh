#!/usr/bin/env bash
# Off-box copy of the production SQLite backups. Runs on Jack's Mac (launchd,
# deploy/launchd/com.urbanlayer.backup-pull.plist), not on the server.
#
# Pulls /opt/urbanlayer/backups/urbanlayer_*.db over SSH with a dedicated key
# that the server only accepts for read-only rrsync of that folder (see
# deploy/hardening-runbook.md section 8c), so the key has no passphrase and
# can't open a shell. Keeps the newest KEEP copies locally, checks the newest
# one opens as a sound SQLite database, and raises a macOS notification if it
# is missing, corrupt, or older than MAX_AGE_HOURS (i.e. the server's nightly
# backup has stopped).
#
# Usage: ./scripts/pull_backups.sh [dest_dir] [keep_count]
# Env:   BACKUP_HOST (an ~/.ssh/config alias, default urbanlayer-backup, that
#        sets HostName, User jack, IdentityFile to the pull key and
#        IdentitiesOnly yes), MAX_AGE_HOURS

set -euo pipefail

DEST="${1:-$HOME/Backups/urbanlayer}"
KEEP="${2:-60}"
HOST="${BACKUP_HOST:-urbanlayer-backup}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-36}"

alarm() {
    echo "WARNING: $1" >&2
    osascript -e "display notification \"$1\" with title \"UrbanLayer backup\"" 2>/dev/null || true
}

umask 077
mkdir -p "$DEST"
echo "--- $(date '+%Y-%m-%d %H:%M:%S') pulling from $HOST"

# The server's forced command (rrsync -ro) roots the path at the backups dir.
# A remote glob, not -r with --include/--exclude: macOS's openrsync sends
# `--dirs` for those, which rrsync rejects. DEST is mode 700, so the copies'
# own 644 mode doesn't expose them.
if ! rsync -t \
        -e "ssh -o BatchMode=yes -o ConnectTimeout=20" \
        "$HOST:./urbanlayer_*.db" "$DEST/"; then
    alarm "Pull from the server failed (see ~/Library/Logs/urbanlayer-backup-pull.log)"
    exit 1
fi

# Prune by name (timestamped), never by mtime: if the server stops producing
# backups, the old copies here must survive.
copies() { find "$DEST" -maxdepth 1 -name 'urbanlayer_*.db' | sort -r; }
copies | tail -n +$((KEEP + 1)) | xargs -r rm -f

NEWEST=$(copies | head -1)
if [ -z "$NEWEST" ]; then
    alarm "No backups found after the pull"
    exit 1
fi

# immutable=1 opens it without touching the file (macOS's `sqlite3 -readonly`
# fails on these copies with "unable to open database file").
CHECK=$(sqlite3 "file:$NEWEST?immutable=1" 'PRAGMA quick_check;' 2>&1 || true)
if [ "$CHECK" != "ok" ]; then
    alarm "Newest backup $(basename "$NEWEST") failed quick_check: $CHECK"
    exit 1
fi

# The name carries the server's UTC timestamp: urbanlayer_YYYYMMDD_HHMMSS.db
STAMP=$(basename "$NEWEST" .db | sed 's/^urbanlayer_//')
BACKUP_EPOCH=$(TZ=UTC date -j -f '%Y%m%d_%H%M%S' "$STAMP" +%s)
AGE_HOURS=$(( ($(date +%s) - BACKUP_EPOCH) / 3600 ))
echo "Newest: $(basename "$NEWEST") (${AGE_HOURS}h old, quick_check ok); $(copies | wc -l | tr -d ' ') copies kept"
if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
    alarm "Newest server backup is ${AGE_HOURS}h old: the nightly cron may have stopped"
fi
