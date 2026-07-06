"""SQLite persistence layer for conversations and messages."""

from __future__ import annotations

import json
import logging
import secrets
import time
from pathlib import Path
from typing import Any

import aiosqlite

from backend.config import get_settings

log = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None

_SCHEMA_VERSION = 14

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    context_json    TEXT,
    plan_json       TEXT,
    map_data_json   TEXT,
    map_fetched_at  INTEGER,
    position        INTEGER NOT NULL,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, position);

CREATE TABLE IF NOT EXISTS uploads (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      INTEGER,
    storage_path    TEXT,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_uploads_conv ON uploads(conversation_id);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
"""

_SCHEMA_V2 = """\
CREATE TABLE IF NOT EXISTS llm_calls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_group       TEXT NOT NULL,
    conversation_id     TEXT,
    phase               TEXT NOT NULL
        CHECK(phase IN ('conversation', 'router', 'synthesizer')),
    model               TEXT NOT NULL,
    input_tokens        INTEGER NOT NULL,
    output_tokens       INTEGER NOT NULL,
    cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_create_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms         INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ok'
        CHECK(status IN ('ok', 'error')),
    error_message       TEXT,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_created ON llm_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_group ON llm_calls(request_group);

CREATE TABLE IF NOT EXISTS request_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_group       TEXT NOT NULL UNIQUE,
    conversation_id     TEXT,
    user_message        TEXT NOT NULL,
    intent              TEXT,
    community_area      INTEGER,
    community_area_name TEXT,
    sources             TEXT,
    total_duration_ms   INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ok',
    error_message       TEXT,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_request_logs_created ON request_logs(created_at);
"""

_SCHEMA_V4 = """\
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    picture_url TEXT,
    google_id   TEXT NOT NULL UNIQUE,
    tier        TEXT NOT NULL DEFAULT 'free'
        CHECK(tier IN ('free', 'premium', 'admin')),
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  INTEGER NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
"""


_SCHEMA_V6 = """\
CREATE TABLE IF NOT EXISTS conversation_shares (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    token           TEXT NOT NULL UNIQUE,
    created_by      TEXT,
    created_at      INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shares_token ON conversation_shares(token);
CREATE INDEX IF NOT EXISTS idx_shares_conv ON conversation_shares(conversation_id);
"""


async def _migrate_v12(db: aiosqlite.Connection) -> None:
    """Rebuild report_purchases with a nullable user_id (ON DELETE SET NULL).

    Account deletion must not destroy purchase records — Stripe holds the
    canonical financial trail, but admin revenue metrics read these rows.
    The v9 table pinned user_id NOT NULL ON DELETE CASCADE, so deleting a
    user row would silently drop their purchases; SET NULL turns the same
    delete into an automatic tombstone.
    """
    cur = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='report_purchases'"
    )
    row = await cur.fetchone()
    if row and "ON DELETE SET NULL" in (row[0] or ""):
        return
    await db.executescript("""\
CREATE TABLE report_purchases_v12 (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               TEXT REFERENCES users(id) ON DELETE SET NULL,
    stripe_session_id     TEXT UNIQUE,
    stripe_payment_intent TEXT,
    address               TEXT,
    lat                   REAL NOT NULL,
    lon                   REAL NOT NULL,
    amount_cents          INTEGER NOT NULL DEFAULT 2500,
    status                TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'completed', 'refunded')),
    created_at            INTEGER NOT NULL,
    completed_at          INTEGER,
    pin                   TEXT
);
INSERT INTO report_purchases_v12
    (id, user_id, stripe_session_id, stripe_payment_intent, address, lat, lon,
     amount_cents, status, created_at, completed_at, pin)
  SELECT id, user_id, stripe_session_id, stripe_payment_intent, address, lat, lon,
         amount_cents, status, created_at, completed_at, pin
  FROM report_purchases;
DROP TABLE report_purchases;
ALTER TABLE report_purchases_v12 RENAME TO report_purchases;
CREATE INDEX IF NOT EXISTS idx_rp_user ON report_purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_rp_location ON report_purchases(user_id, lat, lon);
CREATE INDEX IF NOT EXISTS idx_rp_session ON report_purchases(stripe_session_id);
CREATE INDEX IF NOT EXISTS idx_rp_user_pin ON report_purchases(user_id, pin);
""")


async def _migrate_v13(db: aiosqlite.Connection) -> None:
    """Newsletter subscribers — the owned email channel. One row per email;
    source records which surface captured it (footer, scorecard, …)."""
    await db.executescript("""
CREATE TABLE IF NOT EXISTS subscribers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT NOT NULL UNIQUE,
    source     TEXT,
    created_at INTEGER NOT NULL
);
""")


async def _migrate_v14(db: aiosqlite.Connection) -> None:
    """Early-adopter vouchers: time-boxed complimentary premium.

    users.premium_until (epoch ms) grants premium while in the future —
    deliberately a separate column from tier, so Stripe webhooks (which write
    tier) can never clobber a comp grant and expiry needs no revocation job.
    """
    cur = await db.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in await cur.fetchall()}
    if "premium_until" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN premium_until INTEGER")
    await db.executescript("""\
CREATE TABLE IF NOT EXISTS vouchers (
    code            TEXT PRIMARY KEY,
    label           TEXT,
    duration_days   INTEGER NOT NULL,
    max_redemptions INTEGER NOT NULL DEFAULT 1,
    disabled        INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS voucher_redemptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_code TEXT NOT NULL REFERENCES vouchers(code),
    user_id      TEXT NOT NULL,
    redeemed_at  INTEGER NOT NULL,
    UNIQUE(voucher_code, user_id)
);

CREATE INDEX IF NOT EXISTS idx_vr_code ON voucher_redemptions(voucher_code);
""")


async def _migrate_v11(db: aiosqlite.Connection) -> None:
    """Add nullable pin column to report_purchases — entitlement keys on the
    parcel PIN when known. Legacy pin-less rows stay entitled via the
    coordinate match in has_purchased_report; no backfill."""
    cur = await db.execute("PRAGMA table_info(report_purchases)")
    cols = {row[1] for row in await cur.fetchall()}
    if "pin" not in cols:
        await db.execute("ALTER TABLE report_purchases ADD COLUMN pin TEXT")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_rp_user_pin ON report_purchases(user_id, pin)"
    )


async def _migrate_v10(db: aiosqlite.Connection) -> None:
    """Add events table for usage analytics."""
    await db.executescript("""\
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    visitor_id TEXT,
    user_id    TEXT,
    event_name TEXT NOT NULL,
    event_data TEXT,
    page       TEXT,
    address    TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_name_ts ON events(event_name, created_at);
CREATE INDEX IF NOT EXISTS idx_events_visitor_ts ON events(visitor_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(created_at);
""")


async def _migrate_v9(db: aiosqlite.Connection) -> None:
    """Add report_purchases table for a la carte report sales."""
    await db.executescript("""\
CREATE TABLE IF NOT EXISTS report_purchases (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_session_id     TEXT UNIQUE,
    stripe_payment_intent TEXT,
    address               TEXT,
    lat                   REAL NOT NULL,
    lon                   REAL NOT NULL,
    amount_cents          INTEGER NOT NULL DEFAULT 2500,
    status                TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'completed', 'refunded')),
    created_at            INTEGER NOT NULL,
    completed_at          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_rp_user ON report_purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_rp_location ON report_purchases(user_id, lat, lon);
CREATE INDEX IF NOT EXISTS idx_rp_session ON report_purchases(stripe_session_id);
""")


async def _migrate_v8(db: aiosqlite.Connection) -> None:
    """Add language column to conversations and request_logs tables."""
    for table in ("conversations", "request_logs"):
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cur.fetchall()}
        if "language" not in cols:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN language TEXT DEFAULT 'en'"
            )


async def _migrate_v7(db: aiosqlite.Connection) -> None:
    """Add Stripe columns to users table."""
    cur = await db.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in await cur.fetchall()}
    if "stripe_customer_id" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    if "stripe_subscription_id" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")


async def _migrate_v6(db: aiosqlite.Connection) -> None:
    """Add conversation_shares table for shareable links."""
    await db.executescript(_SCHEMA_V6)


async def _migrate_v4(db: aiosqlite.Connection) -> None:
    """Add users and refresh_tokens tables; add user_id to request_logs and llm_calls."""
    await db.executescript(_SCHEMA_V4)
    for table in ("request_logs", "llm_calls"):
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cur.fetchall()}
        if "user_id" not in cols:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")


async def _migrate_v5(db: aiosqlite.Connection) -> None:
    """Add user_id to conversations table for per-user scoping."""
    cur = await db.execute("PRAGMA table_info(conversations)")
    cols = {row[1] for row in await cur.fetchall()}
    if "user_id" not in cols:
        await db.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)"
        )


async def _migrate_v3(db: aiosqlite.Connection) -> None:
    """Add summary_json column if it doesn't already exist."""
    cur = await db.execute("PRAGMA table_info(messages)")
    cols = {row[1] for row in await cur.fetchall()}
    if "summary_json" not in cols:
        await db.execute("ALTER TABLE messages ADD COLUMN summary_json TEXT")


async def init_db() -> None:
    """Open the database and create tables if needed."""
    global _db
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _db.executescript(_SCHEMA)

    cur = await _db.execute("SELECT version FROM schema_version")
    row = await cur.fetchone()
    if row is None:
        await _db.execute("INSERT INTO schema_version VALUES (?)", (_SCHEMA_VERSION,))
        await _db.executescript(_SCHEMA_V2)
        await _migrate_v3(_db)
        await _migrate_v4(_db)
        await _migrate_v5(_db)
        await _migrate_v6(_db)
        await _migrate_v7(_db)
        await _migrate_v8(_db)
        await _migrate_v9(_db)
        await _migrate_v10(_db)
        await _migrate_v11(_db)
        await _migrate_v12(_db)
        await _migrate_v13(_db)
        await _migrate_v14(_db)
        await _db.commit()
    else:
        version = row[0]
        start_version = version
        if version < 2:
            await _db.executescript(_SCHEMA_V2)
            version = 2
        if version < 3:
            await _migrate_v3(_db)
            version = 3
        if version < 4:
            await _migrate_v4(_db)
            version = 4
        if version < 5:
            await _migrate_v5(_db)
            version = 5
        if version < 6:
            await _migrate_v6(_db)
            version = 6
        if version < 7:
            await _migrate_v7(_db)
            version = 7
        if version < 8:
            await _migrate_v8(_db)
            version = 8
        if version < 9:
            await _migrate_v9(_db)
            version = 9
        if version < 10:
            await _migrate_v10(_db)
            version = 10
        if version < 11:
            await _migrate_v11(_db)
            version = 11
        if version < 12:
            await _migrate_v12(_db)
            version = 12
        if version < 13:
            await _migrate_v13(_db)
            version = 13
        if version < 14:
            await _migrate_v14(_db)
            version = 14
        # Compare against the STARTING version: after the chain runs, the local
        # `version` always equals _SCHEMA_VERSION, so the old `version !=
        # _SCHEMA_VERSION` check never fired and the stamp was never persisted —
        # every boot re-ran the (idempotent) migrations from the stale stamp.
        if start_version != version:
            await _db.execute(
                "UPDATE schema_version SET version = ?", (version,)
            )
            await _db.commit()
            log.info(
                "Migrated database schema from v%d to v%d", start_version, version
            )


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


def _get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _db


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

async def list_conversations(user_id: str | None = None) -> list[dict]:
    db = _get_db()
    if user_id:
        cur = await db.execute(
            """
            SELECT c.id, c.title, c.language, c.created_at, c.updated_at,
                   COUNT(CASE WHEN m.role = 'user' THEN 1 END) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = ? OR c.user_id IS NULL
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (user_id,),
        )
    else:
        cur = await db.execute(
            """
            SELECT c.id, c.title, c.language, c.created_at, c.updated_at,
                   COUNT(CASE WHEN m.role = 'user' THEN 1 END) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """
        )
    rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "language": r["language"] or "en",
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"],
        }
        for r in rows
    ]


async def get_conversation(
    conv_id: str, user_id: str | None = None,
) -> dict | None:
    db = _get_db()
    if user_id:
        cur = await db.execute(
            "SELECT id, title, language, created_at, updated_at FROM conversations "
            "WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
            (conv_id, user_id),
        )
    else:
        cur = await db.execute(
            "SELECT id, title, language, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        )
    conv = await cur.fetchone()
    if conv is None:
        return None

    cur = await db.execute(
        "SELECT role, content, context_json, plan_json, map_data_json, map_fetched_at, summary_json "
        "FROM messages WHERE conversation_id = ? ORDER BY position",
        (conv_id,),
    )
    rows = await cur.fetchall()
    messages = []
    for r in rows:
        msg: dict[str, Any] = {"role": r["role"], "content": r["content"]}
        if r["context_json"]:
            msg["context"] = json.loads(r["context_json"])
        if r["plan_json"]:
            msg["plan"] = json.loads(r["plan_json"])
        if r["map_data_json"]:
            msg["map_data"] = json.loads(r["map_data_json"])
        if r["map_fetched_at"]:
            msg["map_fetched_at"] = r["map_fetched_at"]
        if r["summary_json"]:
            msg["summary"] = json.loads(r["summary_json"])
        messages.append(msg)

    return {
        "id": conv["id"],
        "title": conv["title"],
        "language": conv["language"] or "en",
        "messages": messages,
        "created_at": conv["created_at"],
        "updated_at": conv["updated_at"],
    }


async def create_conversation(
    conv_id: str, title: str, user_id: str | None = None,
    language: str = "en",
) -> dict:
    db = _get_db()
    now = _now_ms()
    await db.execute(
        "INSERT INTO conversations (id, title, user_id, language, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, title, user_id, language, now, now),
    )
    await db.commit()
    return {"id": conv_id, "title": title, "language": language, "created_at": now, "updated_at": now}


async def save_messages(conv_id: str, messages: list[dict]) -> None:
    db = _get_db()

    cur = await db.execute(
        "SELECT COALESCE(MAX(position), -1) FROM messages WHERE conversation_id = ?",
        (conv_id,),
    )
    row = await cur.fetchone()
    next_pos = row[0] + 1

    now = _now_ms()
    for i, msg in enumerate(messages):
        await db.execute(
            """
            INSERT INTO messages
              (conversation_id, role, content, context_json, plan_json,
               map_data_json, map_fetched_at, summary_json, position, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                msg["role"],
                msg["content"],
                json.dumps(msg["context"]) if msg.get("context") else None,
                json.dumps(msg["plan"]) if msg.get("plan") else None,
                json.dumps(msg["map_data"]) if msg.get("map_data") else None,
                msg.get("map_fetched_at"),
                json.dumps(msg["summary"]) if msg.get("summary") else None,
                next_pos + i,
                now,
            ),
        )

    await db.execute(
        "UPDATE conversations SET updated_at = ?, title = COALESCE(?, title) WHERE id = ?",
        (now, _title_from_messages(conv_id, messages), conv_id),
    )
    await db.commit()


def _title_from_messages(conv_id: str, messages: list[dict]) -> str | None:
    """Generate a title from the first user message if this is the first save."""
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"].strip()
            return content[:47] + "..." if len(content) > 50 else content
    return None


async def update_message_map_data(
    conv_id: str, position: int, map_data: dict, fetched_at: int | None = None,
) -> None:
    db = _get_db()
    await db.execute(
        """
        UPDATE messages
        SET map_data_json = ?, map_fetched_at = ?
        WHERE conversation_id = ? AND position = ?
        """,
        (json.dumps(map_data), fetched_at or _now_ms(), conv_id, position),
    )
    await db.commit()


async def delete_conversation(
    conv_id: str, user_id: str | None = None,
) -> bool:
    conn = _get_db()
    # CASCADE handles DB rows; clean up files on disk
    try:
        import shutil
        settings = get_settings()
        upload_dir = settings.upload_dir / conv_id
        if upload_dir.is_dir():
            shutil.rmtree(upload_dir)
    except Exception:
        pass
    if user_id:
        cur = await conn.execute(
            "DELETE FROM conversations WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
            (conv_id, user_id),
        )
    else:
        cur = await conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    await conn.commit()
    return cur.rowcount > 0


async def clear_all_conversations(user_id: str | None = None) -> None:
    conn = _get_db()
    try:
        import shutil
        settings = get_settings()
        if settings.upload_dir.is_dir():
            shutil.rmtree(settings.upload_dir)
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if user_id:
        await conn.execute(
            "DELETE FROM conversations WHERE user_id = ? OR user_id IS NULL",
            (user_id,),
        )
    else:
        await conn.execute("DELETE FROM conversations")
    await conn.commit()


async def get_turn_summaries(conv_id: str) -> list[dict]:
    """Load all TurnSummary objects for a conversation."""
    db = _get_db()
    cur = await db.execute(
        "SELECT summary_json FROM messages WHERE conversation_id = ? AND summary_json IS NOT NULL ORDER BY position",
        (conv_id,),
    )
    rows = await cur.fetchall()
    return [json.loads(r["summary_json"]) for r in rows]


async def count_user_messages(conv_id: str) -> int:
    db = _get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'user'",
        (conv_id,),
    )
    row = await cur.fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Conversation sharing
# ---------------------------------------------------------------------------


async def create_share_token(
    conv_id: str, user_id: str,
) -> dict:
    db = _get_db()
    cur = await db.execute(
        "SELECT id FROM conversations WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
        (conv_id, user_id),
    )
    if not await cur.fetchone():
        return {}
    await db.execute(
        "DELETE FROM conversation_shares WHERE conversation_id = ?",
        (conv_id,),
    )
    token = secrets.token_urlsafe(22)
    now = _now_ms()
    await db.execute(
        "INSERT INTO conversation_shares (conversation_id, token, created_by, created_at) VALUES (?, ?, ?, ?)",
        (conv_id, token, user_id, now),
    )
    await db.commit()
    return {"token": token, "conversation_id": conv_id, "created_at": now}


async def get_share(token: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT conversation_id, token, created_by, created_at FROM conversation_shares WHERE token = ?",
        (token,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_conversation_share(conv_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT token, created_by, created_at FROM conversation_shares WHERE conversation_id = ?",
        (conv_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def revoke_share(conv_id: str, user_id: str) -> bool:
    db = _get_db()
    cur = await db.execute(
        """
        DELETE FROM conversation_shares
        WHERE conversation_id = ?
          AND conversation_id IN (SELECT id FROM conversations WHERE user_id = ? OR user_id IS NULL)
        """,
        (conv_id, user_id),
    )
    await db.commit()
    return cur.rowcount > 0


async def get_shared_conversation(token: str) -> dict | None:
    share = await get_share(token)
    if not share:
        return None
    return await get_conversation(share["conversation_id"])


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

async def save_upload(
    upload_id: str,
    conversation_id: str,
    filename: str,
    mime_type: str | None,
    size_bytes: int,
    storage_path: str,
    message_position: int | None = None,
) -> dict:
    db = _get_db()
    now = _now_ms()
    await db.execute(
        """
        INSERT INTO uploads (id, conversation_id, filename, mime_type, size_bytes, storage_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (upload_id, conversation_id, filename, mime_type, size_bytes, storage_path, now),
    )
    await db.commit()
    return {
        "id": upload_id,
        "conversation_id": conversation_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "created_at": now,
    }


async def get_upload(upload_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT id, conversation_id, filename, mime_type, size_bytes, storage_path, created_at "
        "FROM uploads WHERE id = ?",
        (upload_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return dict(row)


async def get_uploads_for_conversation(conv_id: str) -> list[dict]:
    db = _get_db()
    cur = await db.execute(
        "SELECT id, conversation_id, filename, mime_type, size_bytes, created_at "
        "FROM uploads WHERE conversation_id = ? ORDER BY created_at",
        (conv_id,),
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def delete_upload(upload_id: str) -> bool:
    db = _get_db()
    cur = await db.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    await db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Bulk import (localStorage migration)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LLM call logging
# ---------------------------------------------------------------------------

async def save_llm_call(
    *,
    request_group: str,
    conversation_id: str | None,
    phase: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
    duration_ms: int,
    status: str = "ok",
    error_message: str | None = None,
) -> None:
    db = _get_db()
    await db.execute(
        """
        INSERT INTO llm_calls
          (request_group, conversation_id, phase, model, input_tokens, output_tokens,
           cache_read_tokens, cache_create_tokens, duration_ms, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_group, conversation_id, phase, model,
            input_tokens, output_tokens, cache_read_tokens, cache_create_tokens,
            duration_ms, status, error_message, _now_ms(),
        ),
    )
    await db.commit()


async def save_request_log(
    *,
    request_group: str,
    conversation_id: str | None,
    user_message: str,
    intent: str | None = None,
    community_area: int | None = None,
    community_area_name: str | None = None,
    sources: list[str] | None = None,
    total_duration_ms: int,
    status: str = "ok",
    error_message: str | None = None,
    language: str = "en",
) -> None:
    db = _get_db()
    await db.execute(
        """
        INSERT OR IGNORE INTO request_logs
          (request_group, conversation_id, user_message, intent, community_area,
           community_area_name, sources, total_duration_ms, status, error_message,
           language, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_group, conversation_id, user_message, intent,
            community_area, community_area_name,
            json.dumps(sources) if sources else None,
            total_duration_ms, status, error_message, language, _now_ms(),
        ),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Admin queries
# ---------------------------------------------------------------------------

def _period_cutoff_ms(period: str) -> int | None:
    """Convert a period string to a millisecond cutoff timestamp."""
    if period == "all":
        return None
    import datetime
    now = time.time() * 1000
    if period == "today":
        midnight = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int(midnight.timestamp() * 1000)
    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 30)
    return int(now - days * 86_400_000)


async def get_admin_overview(period: str) -> dict:
    db = _get_db()
    cutoff = _period_cutoff_ms(period)
    where = "WHERE created_at >= ?" if cutoff else ""
    params: tuple = (cutoff,) if cutoff else ()

    cur = await db.execute(
        f"""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) as error_count
        FROM llm_calls {where}
        """,
        params,
    )
    row = await cur.fetchone()

    cur2 = await db.execute(
        f"""
        SELECT model,
            COUNT(*) as count,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens
        FROM llm_calls {where}
        GROUP BY model
        """,
        params,
    )
    by_model = {
        r["model"]: {
            "count": r["count"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
        }
        for r in await cur2.fetchall()
    }

    cur3 = await db.execute(
        f"""
        SELECT phase,
            COUNT(*) as count,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(AVG(duration_ms), 0) as avg_duration_ms
        FROM llm_calls {where}
        GROUP BY phase
        """,
        params,
    )
    by_phase = {
        r["phase"]: {
            "count": r["count"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "avg_duration_ms": round(r["avg_duration_ms"]),
        }
        for r in await cur3.fetchall()
    }

    # Count distinct request groups for "total requests"
    cur4 = await db.execute(
        f"SELECT COUNT(DISTINCT request_group) as cnt FROM llm_calls {where}",
        params,
    )
    total_requests = (await cur4.fetchone())["cnt"]

    return {
        "total_requests": total_requests,
        "total_llm_calls": row["count"],
        "total_input_tokens": row["input_tokens"],
        "total_output_tokens": row["output_tokens"],
        "total_cache_read_tokens": row["cache_read_tokens"],
        "error_count": row["error_count"],
        "by_model": by_model,
        "by_phase": by_phase,
    }


async def get_admin_timeseries(period: str, bucket: str = "day") -> list[dict]:
    db = _get_db()
    cutoff = _period_cutoff_ms(period)
    where = "WHERE created_at >= ?" if cutoff else ""
    params: tuple = (cutoff,) if cutoff else ()

    if bucket == "hour":
        bucket_expr = "strftime('%Y-%m-%dT%H:00', created_at / 1000, 'unixepoch')"
    else:
        bucket_expr = "strftime('%Y-%m-%d', created_at / 1000, 'unixepoch')"

    cur = await db.execute(
        f"""
        SELECT {bucket_expr} as bucket,
            COUNT(DISTINCT request_group) as request_count,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
            COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) as error_count
        FROM llm_calls {where}
        GROUP BY bucket
        ORDER BY bucket
        """,
        params,
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_admin_latency(period: str) -> list[dict]:
    db = _get_db()
    cutoff = _period_cutoff_ms(period)
    where = "WHERE status = 'ok'" + (" AND created_at >= ?" if cutoff else "")
    params: tuple = (cutoff,) if cutoff else ()

    phases = ["conversation", "router", "synthesizer"]
    results = []
    for phase in phases:
        phase_where = where + " AND phase = ?"
        phase_params = params + (phase,)
        cur = await db.execute(
            f"""
            SELECT duration_ms FROM llm_calls {phase_where}
            ORDER BY duration_ms
            """,
            phase_params,
        )
        rows = [r["duration_ms"] for r in await cur.fetchall()]
        if not rows:
            continue
        n = len(rows)
        results.append({
            "phase": phase,
            "p50_ms": rows[n // 2],
            "p90_ms": rows[int(n * 0.9)],
            "p99_ms": rows[min(int(n * 0.99), n - 1)],
            "count": n,
        })

    return results


async def get_admin_conversation_stats() -> dict:
    db = _get_db()
    cur = await db.execute("SELECT COUNT(*) as cnt FROM conversations")
    total_convs = (await cur.fetchone())["cnt"]

    cur = await db.execute("SELECT COUNT(*) as cnt FROM messages")
    total_msgs = (await cur.fetchone())["cnt"]

    import datetime
    midnight = datetime.datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    midnight_ms = int(midnight.timestamp() * 1000)
    cur = await db.execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE created_at >= ?",
        (midnight_ms,),
    )
    today_convs = (await cur.fetchone())["cnt"]

    return {
        "total_conversations": total_convs,
        "total_messages": total_msgs,
        "avg_messages_per_conversation": round(total_msgs / total_convs, 1) if total_convs else 0,
        "conversations_today": today_convs,
    }


async def get_admin_request_logs(limit: int = 50, offset: int = 0) -> list[dict]:
    db = _get_db()
    cur = await db.execute(
        """
        SELECT id, request_group, conversation_id, user_message, intent,
               community_area_name, sources, total_duration_ms, status,
               error_message, created_at
        FROM request_logs
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    rows = await cur.fetchall()
    results = []
    for r in rows:
        entry = dict(r)
        entry["sources"] = json.loads(entry["sources"]) if entry["sources"] else []
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Users & auth
# ---------------------------------------------------------------------------

async def upsert_user(
    user_id: str,
    email: str,
    name: str,
    picture_url: str | None,
    google_id: str,
) -> dict:
    db = _get_db()
    now = _now_ms()
    await db.execute(
        """
        INSERT INTO users (id, email, name, picture_url, google_id, tier, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'free', ?, ?)
        ON CONFLICT(google_id) DO UPDATE SET
            email = excluded.email,
            name = excluded.name,
            picture_url = excluded.picture_url,
            updated_at = ?
        """,
        (user_id, email, name, picture_url, google_id, now, now, now),
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    row = await cur.fetchone()
    return dict(row)


async def get_user_by_id(user_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_google_id(google_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_stripe_customer(customer_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_email(email: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT * FROM users WHERE lower(email) = lower(?)", (email,)
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def update_user_tier(user_id: str, tier: str) -> None:
    db = _get_db()
    await db.execute(
        "UPDATE users SET tier = ?, updated_at = ? WHERE id = ?",
        (tier, _now_ms(), user_id),
    )
    await db.commit()


async def update_user_stripe(
    user_id: str, customer_id: str, subscription_id: str | None
) -> None:
    db = _get_db()
    await db.execute(
        "UPDATE users SET stripe_customer_id = ?, stripe_subscription_id = ?, updated_at = ? WHERE id = ?",
        (customer_id, subscription_id, _now_ms(), user_id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Vouchers — time-boxed complimentary premium for early adopters
# ---------------------------------------------------------------------------

class VoucherError(Exception):
    """Redemption failure with a machine-readable reason:
    'not_found' | 'already_redeemed' | 'exhausted'."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def set_premium_until(user_id: str, until_ms: int | None) -> None:
    db = _get_db()
    await db.execute(
        "UPDATE users SET premium_until = ?, updated_at = ? WHERE id = ?",
        (until_ms, _now_ms(), user_id),
    )
    await db.commit()


async def create_voucher(
    code: str,
    label: str | None,
    duration_days: int,
    max_redemptions: int = 1,
) -> dict:
    db = _get_db()
    await db.execute(
        """
        INSERT INTO vouchers (code, label, duration_days, max_redemptions, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (code, label, duration_days, max_redemptions, _now_ms()),
    )
    await db.commit()
    return (await get_voucher(code)) or {}


async def get_voucher(code: str) -> dict | None:
    db = _get_db()
    cur = await db.execute("SELECT * FROM vouchers WHERE code = ?", (code,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def list_vouchers() -> list[dict]:
    """All vouchers, newest first, each with its redemption history."""
    db = _get_db()
    cur = await db.execute("SELECT * FROM vouchers ORDER BY created_at DESC")
    vouchers = [dict(row) for row in await cur.fetchall()]
    for v in vouchers:
        cur = await db.execute(
            """
            SELECT vr.user_id, vr.redeemed_at, u.email, u.name
            FROM voucher_redemptions vr
            LEFT JOIN users u ON u.id = vr.user_id
            WHERE vr.voucher_code = ?
            ORDER BY vr.redeemed_at
            """,
            (v["code"],),
        )
        v["redemptions"] = [dict(r) for r in await cur.fetchall()]
    return vouchers


async def redeem_voucher(code: str, user_id: str) -> int:
    """Redeem a voucher for a user; returns the new premium_until (epoch ms).

    Extends from max(now, existing premium_until) so stacking a second code
    adds its full duration. Raises VoucherError on any validation failure.
    """
    db = _get_db()
    voucher = await get_voucher(code)
    if voucher is None or voucher["disabled"]:
        raise VoucherError("not_found")

    cur = await db.execute(
        "SELECT COUNT(*), MAX(user_id = ?) FROM voucher_redemptions WHERE voucher_code = ?",
        (user_id, code),
    )
    count, already = await cur.fetchone()
    if already:
        raise VoucherError("already_redeemed")
    if count >= voucher["max_redemptions"]:
        raise VoucherError("exhausted")

    user = await get_user_by_id(user_id)
    if user is None:
        raise VoucherError("not_found")

    now = _now_ms()
    base = max(now, user.get("premium_until") or 0)
    until = base + voucher["duration_days"] * 86_400_000
    await db.execute(
        "INSERT INTO voucher_redemptions (voucher_code, user_id, redeemed_at) VALUES (?, ?, ?)",
        (code, user_id, now),
    )
    await db.execute(
        "UPDATE users SET premium_until = ?, updated_at = ? WHERE id = ?",
        (until, now, user_id),
    )
    await db.commit()
    return until


async def save_refresh_token(
    user_id: str, token_hash: str, expires_at: int,
) -> None:
    db = _get_db()
    await db.execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, token_hash, expires_at, _now_ms()),
    )
    await db.commit()


async def get_refresh_token(token_hash: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT * FROM refresh_tokens WHERE token_hash = ? AND revoked = 0 AND expires_at > ?",
        (token_hash, _now_ms()),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def revoke_refresh_token(token_hash: str) -> None:
    db = _get_db()
    await db.execute(
        "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?", (token_hash,),
    )
    await db.commit()


async def revoke_all_user_refresh_tokens(user_id: str) -> None:
    db = _get_db()
    await db.execute(
        "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (user_id,),
    )
    await db.commit()


async def delete_user_account(user_id: str) -> dict:
    """Permanently delete a user and all their content.

    Conversations cascade messages/uploads/shares (FK); the user row cascades
    refresh_tokens and tombstones report_purchases (user_id SET NULL — the
    purchase rows are financial history, Stripe keeps the canonical copy).
    request_logs hold raw message text → deleted; llm_calls hold only token
    counts → unlinked. Upload files on disk are removed best-effort AFTER the
    commit so a filesystem failure can't leave dangling DB rows.

    Only rows with user_id = ? are touched — legacy user_id IS NULL rows
    (pre-auth data) are shared, not this user's.
    """
    conn = _get_db()
    cur = await conn.execute(
        "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
    )
    conv_ids = [r["id"] for r in await cur.fetchall()]

    await conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    await conn.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
    await conn.execute("DELETE FROM request_logs WHERE user_id = ?", (user_id,))
    await conn.execute(
        "UPDATE llm_calls SET user_id = NULL WHERE user_id = ?", (user_id,)
    )
    await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await conn.commit()

    import shutil
    settings = get_settings()
    for conv_id in conv_ids:
        try:
            upload_dir = settings.upload_dir / conv_id
            if upload_dir.is_dir():
                shutil.rmtree(upload_dir)
        except Exception:
            pass

    return {"conversations_deleted": len(conv_ids)}


# ---------------------------------------------------------------------------
# Report purchases (a la carte)
# ---------------------------------------------------------------------------


async def save_report_purchase(
    user_id: str,
    stripe_session_id: str,
    address: str | None,
    lat: float,
    lon: float,
    amount_cents: int = 2500,
    pin: str | None = None,
) -> int:
    """Insert a pending report purchase. Returns the row id."""
    conn = _get_db()
    cur = await conn.execute(
        """
        INSERT INTO report_purchases
          (user_id, stripe_session_id, address, lat, lon, amount_cents, status, created_at, pin)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (user_id, stripe_session_id, address, round(lat, 4), round(lon, 4),
         amount_cents, _now_ms(), pin),
    )
    await conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


async def complete_report_purchase(
    stripe_session_id: str, payment_intent: str | None = None,
) -> dict | None:
    """Mark a purchase as completed. Idempotent — no-op if already completed."""
    conn = _get_db()
    cur = await conn.execute(
        "SELECT * FROM report_purchases WHERE stripe_session_id = ?",
        (stripe_session_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    if row["status"] == "completed":
        return dict(row)
    await conn.execute(
        """
        UPDATE report_purchases
        SET status = 'completed', stripe_payment_intent = ?, completed_at = ?
        WHERE stripe_session_id = ? AND status = 'pending'
        """,
        (payment_intent, _now_ms(), stripe_session_id),
    )
    await conn.commit()
    cur = await conn.execute(
        "SELECT * FROM report_purchases WHERE stripe_session_id = ?",
        (stripe_session_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def has_purchased_report(
    user_id: str, lat: float, lon: float, pin: str | None = None,
) -> bool:
    """Check if user has a completed purchase for this parcel.

    PIN is the primary entitlement key. The coordinate clause is retained
    permanently so legacy pin-less purchase rows stay entitled (no backfill);
    pin=NULL rows never match the pin clause (SQL NULL comparison), so they
    fall through to the coordinate match.
    """
    conn = _get_db()
    cur = await conn.execute(
        """
        SELECT 1 FROM report_purchases
        WHERE user_id = ?
          AND (pin = ?
               OR (ROUND(lat, 4) = ROUND(?, 4) AND ROUND(lon, 4) = ROUND(?, 4)))
          AND status = 'completed'
        LIMIT 1
        """,
        (user_id, pin, lat, lon),
    )
    return await cur.fetchone() is not None


async def get_user_report_purchases(user_id: str) -> list[dict]:
    """Return all completed report purchases for a user."""
    conn = _get_db()
    cur = await conn.execute(
        """
        SELECT id, address, pin, lat, lon, amount_cents, created_at, completed_at
        FROM report_purchases
        WHERE user_id = ? AND status = 'completed'
        ORDER BY completed_at DESC
        """,
        (user_id,),
    )
    return [dict(r) for r in await cur.fetchall()]


# ---------------------------------------------------------------------------
# Usage analytics
# ---------------------------------------------------------------------------

async def add_subscriber(email: str, source: str | None = None) -> bool:
    """Store a newsletter subscriber. Returns True if newly added."""
    db = _get_db()
    cur = await db.execute(
        "INSERT OR IGNORE INTO subscribers (email, source, created_at) VALUES (?, ?, ?)",
        (email.strip().lower(), source, _now_ms()),
    )
    await db.commit()
    return cur.rowcount > 0


async def save_events(events: list[dict]) -> None:
    """Batch-insert analytics events. Never raises — logs on failure."""
    try:
        db = _get_db()
        now = _now_ms()
        await db.executemany(
            """
            INSERT INTO events
              (session_id, visitor_id, user_id, event_name, event_data, page, address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e["session_id"],
                    e.get("visitor_id"),
                    e.get("user_id"),
                    e["event_name"],
                    json.dumps(e["event_data"]) if e.get("event_data") else None,
                    e.get("page"),
                    e.get("address"),
                    e.get("timestamp") or now,
                )
                for e in events
            ],
        )
        await db.commit()
    except Exception:
        log.exception("Failed to save %d analytics events", len(events))


async def get_engagement_stats(period: str) -> dict:
    """Return engagement metrics for the admin dashboard."""
    db = _get_db()
    cutoff = _period_cutoff_ms(period)
    ts_filter = "AND created_at >= ?" if cutoff else ""
    where = "WHERE created_at >= ?" if cutoff else ""
    params: tuple = (cutoff,) if cutoff else ()

    def _ev_params(event_name: str) -> tuple:
        return (event_name, cutoff) if cutoff else (event_name,)

    ev_where = f"WHERE event_name = ? {ts_filter}"

    async def _counts_by(event_name: str, json_path: str) -> dict:
        cur = await db.execute(
            f"""
            SELECT json_extract(event_data, ?) as k, COUNT(*) as cnt
            FROM events {ev_where}
            GROUP BY k ORDER BY cnt DESC
            """,
            (json_path, *_ev_params(event_name)),
        )
        return {r["k"]: r["cnt"] for r in await cur.fetchall()}

    investigate_clicks = await _counts_by("investigate_click", "$.card_name")
    hero_address_submits = await _counts_by("hero_address_submit", "$.source")
    hero_librarian_clicks = await _counts_by("hero_librarian_click", "$.source")
    scorecard_bridge_clicks = await _counts_by("scorecard_bridge_click", "$.source")

    # Simple counts
    counts = {}
    for ev_name in ("report_cta_click", "chat_message_sent", "page_view", "sample_report_click"):
        cur = await db.execute(
            f"SELECT COUNT(*) as cnt FROM events {ev_where}",
            _ev_params(ev_name),
        )
        counts[ev_name] = (await cur.fetchone())["cnt"]

    # Report purchases (from existing table, same period)
    rp_where = "WHERE status = 'completed'" + (
        " AND completed_at >= ?" if cutoff else ""
    )
    cur = await db.execute(
        f"SELECT COUNT(*) as cnt FROM report_purchases {rp_where}",
        params,
    )
    report_purchases_count = (await cur.fetchone())["cnt"]

    # Unique visitors
    cur = await db.execute(
        f"SELECT COUNT(DISTINCT visitor_id) as cnt FROM events {where}",
        params,
    )
    unique_visitors = (await cur.fetchone())["cnt"]

    # Returning visitors (2+ sessions on different days)
    cur = await db.execute(
        f"""
        SELECT COUNT(*) as cnt FROM (
            SELECT visitor_id FROM events {where}
            GROUP BY visitor_id
            HAVING COUNT(DISTINCT created_at / 86400000) >= 2
        )
        """,
        params,
    )
    returning_visitors = (await cur.fetchone())["cnt"]

    # Avg days between visits for returning visitors
    cur = await db.execute(
        f"""
        SELECT AVG(span_days) as avg_days FROM (
            SELECT visitor_id,
                (MAX(created_at) - MIN(created_at)) / 86400000.0 as span_days
            FROM events {where}
            GROUP BY visitor_id
            HAVING COUNT(DISTINCT created_at / 86400000) >= 2
        )
        """,
        params,
    )
    row = await cur.fetchone()
    avg_days_between = round(row["avg_days"], 1) if row["avg_days"] else None

    # Scorecard → chat conversion
    cur = await db.execute(
        f"""
        SELECT COUNT(DISTINCT visitor_id) as cnt FROM events
        WHERE event_name = 'page_view' AND page = '/scorecard' {ts_filter}
        """,
        params,
    )
    scorecard_visitors = (await cur.fetchone())["cnt"]

    cur = await db.execute(
        f"""
        SELECT COUNT(*) as cnt FROM (
            SELECT visitor_id FROM events
            WHERE event_name = 'page_view' AND page = '/scorecard' {ts_filter}
            INTERSECT
            SELECT visitor_id FROM events
            WHERE event_name = 'chat_message_sent' {ts_filter}
        )
        """,
        params + params,
    )
    scorecard_and_chat = (await cur.fetchone())["cnt"]
    scorecard_to_chat_rate = (
        round(scorecard_and_chat / scorecard_visitors, 3)
        if scorecard_visitors > 0
        else None
    )

    # Return rate by behavior: investigate users vs non-investigate users
    cur = await db.execute(
        f"""
        SELECT
            CASE WHEN inv.visitor_id IS NOT NULL THEN 'investigated' ELSE 'not_investigated' END as behavior,
            COUNT(*) as total,
            SUM(CASE WHEN days >= 2 THEN 1 ELSE 0 END) as returned
        FROM (
            SELECT visitor_id, COUNT(DISTINCT created_at / 86400000) as days
            FROM events {where}
            GROUP BY visitor_id
        ) v
        LEFT JOIN (
            SELECT DISTINCT visitor_id FROM events
            WHERE event_name = 'investigate_click' {ts_filter}
        ) inv ON v.visitor_id = inv.visitor_id
        GROUP BY behavior
        """,
        params + params,
    )
    return_rate_by_behavior = {}
    for r in await cur.fetchall():
        rate = round(r["returned"] / r["total"], 3) if r["total"] > 0 else 0
        return_rate_by_behavior[r["behavior"]] = {
            "total": r["total"],
            "returned": r["returned"],
            "rate": rate,
        }

    # Page views by page
    cur = await db.execute(
        f"""
        SELECT page, COUNT(*) as cnt FROM events {ev_where}
        GROUP BY page ORDER BY cnt DESC
        """,
        _ev_params("page_view"),
    )
    page_views = {r["page"]: r["cnt"] for r in await cur.fetchall()}

    # Acquisition funnel: distinct visitors reaching each step, in order.
    # purchase_completed / subscription_started are webhook-written (never
    # client-ingested), so the last step can't be inflated by a browser.
    async def _distinct_visitors(*event_names: str) -> int:
        placeholders = ",".join("?" for _ in event_names)
        cur = await db.execute(
            f"""
            SELECT COUNT(DISTINCT visitor_id) as cnt FROM events
            WHERE event_name IN ({placeholders}) {ts_filter}
            """,
            (*event_names, *params),
        )
        return (await cur.fetchone())["cnt"]

    funnel = [
        {"step": "visited", "visitors": unique_visitors},
        {"step": "address_entered", "visitors": await _distinct_visitors("hero_address_submit")},
        {"step": "scorecard_viewed", "visitors": await _distinct_visitors("scorecard_view")},
        {"step": "engaged", "visitors": await _distinct_visitors(
            "investigate_click", "chat_message_sent", "report_cta_click")},
        {"step": "checkout_started", "visitors": await _distinct_visitors("checkout_started")},
        {"step": "purchased", "visitors": await _distinct_visitors(
            "purchase_completed", "subscription_started")},
    ]

    # Acquisition channels from visit_start attribution: utm_source, else
    # referrer host, else "direct" — one channel per distinct visitor,
    # taken from their earliest visit_start in the period.
    cur = await db.execute(
        f"""
        SELECT visitor_id, event_data, MIN(created_at) as first_ts FROM events
        WHERE event_name = 'visit_start' {ts_filter}
        GROUP BY visitor_id
        """,
        params,
    )
    from urllib.parse import urlparse
    channels: dict[str, int] = {}
    for r in await cur.fetchall():
        label = "direct"
        try:
            data = json.loads(r["event_data"]) if r["event_data"] else {}
            first_touch = data.get("first_touch") or {}
            utm = data.get("utm_source") or first_touch.get("utm_source")
            ref = data.get("referrer") or first_touch.get("referrer")
            if utm:
                label = f"utm:{utm}"
            elif ref:
                label = urlparse(ref).netloc or "direct"
        except Exception:
            pass
        channels[label] = channels.get(label, 0) + 1
    channels = dict(sorted(channels.items(), key=lambda kv: kv[1], reverse=True))

    return {
        "investigate_clicks": investigate_clicks,
        "hero_address_submits": hero_address_submits,
        "hero_librarian_clicks": hero_librarian_clicks,
        "scorecard_bridge_clicks": scorecard_bridge_clicks,
        "report_cta_clicks": counts["report_cta_click"],
        "sample_report_clicks": counts["sample_report_click"],
        "report_purchases_count": report_purchases_count,
        "chat_messages": counts["chat_message_sent"],
        "unique_visitors": unique_visitors,
        "returning_visitors": returning_visitors,
        "avg_days_between_visits": avg_days_between,
        "scorecard_to_chat_rate": scorecard_to_chat_rate,
        "return_rate_by_behavior": return_rate_by_behavior,
        "page_views": page_views,
        "funnel": funnel,
        "channels": channels,
    }


# ---------------------------------------------------------------------------
# Bulk import (localStorage migration)
# ---------------------------------------------------------------------------

async def import_conversations(
    conversations: list[dict], user_id: str | None = None,
) -> int:
    """Import conversations from localStorage export. Returns count imported."""
    db = _get_db()
    imported = 0

    for conv in conversations:
        cur = await db.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conv["id"],)
        )
        if await cur.fetchone():
            continue

        await db.execute(
            "INSERT INTO conversations (id, title, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv["id"], conv.get("title", "Imported"), user_id, conv.get("createdAt", _now_ms()), conv.get("updatedAt", _now_ms())),
        )

        for i, msg in enumerate(conv.get("messages", [])):
            context = msg.get("context")
            await db.execute(
                """
                INSERT INTO messages
                  (conversation_id, role, content, context_json, position, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conv["id"],
                    msg["role"],
                    msg["content"],
                    json.dumps(context) if context else None,
                    i,
                    conv.get("createdAt", _now_ms()),
                ),
            )
        imported += 1

    await db.commit()
    return imported
