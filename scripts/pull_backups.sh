#!/usr/bin/env bash
# Off-box copy of the production SQLite backups. Runs on Jack's Mac (launchd,
# deploy/launchd/com.urbanlayer.backup-pull.plist), not on the server.
#
# Pulls /opt/urbanlayer/backups/urbanlayer_*.db, and the stored report PDFs that
# backup_db.sh mirrors into /opt/urbanlayer/backups/reports/, over SSH with a dedicated key
# that the server only accepts for read-only rrsync of that folder (see
# deploy/hardening-runbook.md section 8c), so the key has no passphrase and
# can't open a shell. Keeps the newest KEEP copies locally, checks the newest
# one opens as a sound SQLite database, checks every report original that
# database lists is here with the hash it was stored with, and raises a macOS
# notification if anything is missing, corrupt, or older than MAX_AGE_HOURS
# (i.e. the server's nightly backup has stopped).
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

# Report originals (WS6 M8): the PDF a buyer was sold exists nowhere else. The
# newest database lists every stored original (report_renders, kind 'original',
# path <purchase_id>/<ms>.pdf); each one not yet here is fetched as a single file.
# No recursion: macOS's openrsync turns -r into --dirs and rrsync refuses both
# that and --relative (checked against the server 2026-10-30). The database is
# captured before the server's mirror runs, so every listed file was mirrored the
# same night. A file already here is never fetched again (--ignore-existing), so a
# damaged server copy cannot replace a good local one, and nothing here is ever
# deleted or pruned (account deletion on the server leaves these copies: a
# retention question for Jack, not for this script). Then every listed file must
# match the sha256 it was stored with.
mkdir -p "$DEST/reports"
MISSING=0; BAD=0; CHECKED=0; FETCHED=0
while IFS='|' read -r REL SHA; do
    [ -n "$REL" ] || continue
    CHECKED=$((CHECKED + 1))
    case "$REL" in
        [0-9]*/[0-9]*.pdf) ;;
        *) BAD=$((BAD + 1)); echo "unexpected report path in the database: $REL" >&2; continue ;;
    esac
    case "$REL" in *..*|*/*/*) BAD=$((BAD + 1)); echo "unexpected report path in the database: $REL" >&2; continue ;; esac
    if [ ! -f "$DEST/reports/$REL" ]; then
        mkdir -p "$DEST/reports/$(dirname "$REL")"
        if rsync -t --ignore-existing -e "ssh -o BatchMode=yes -o ConnectTimeout=20" \
                "$HOST:./reports/$REL" "$DEST/reports/$(dirname "$REL")/"; then
            FETCHED=$((FETCHED + 1))
        fi
    fi
    if [ ! -f "$DEST/reports/$REL" ]; then
        MISSING=$((MISSING + 1)); echo "missing report PDF: $REL" >&2
    elif [ "$(shasum -a 256 "$DEST/reports/$REL" | cut -d' ' -f1)" != "$SHA" ]; then
        BAD=$((BAD + 1)); echo "report PDF hash differs: $REL" >&2
    fi
done < <(sqlite3 "file:$NEWEST?immutable=1" \
    "SELECT pdf_path, pdf_sha256 FROM report_renders WHERE kind = 'original' AND pdf_path IS NOT NULL;" 2>/dev/null || true)
echo "Report originals: $CHECKED listed, $FETCHED fetched now, $((CHECKED - MISSING - BAD)) present and matching"
if [ "$MISSING" -gt 0 ] || [ "$BAD" -gt 0 ]; then
    alarm "Report PDFs: $MISSING missing, $BAD with a different hash or path, of $CHECKED in the newest backup"
    exit 1
fi
