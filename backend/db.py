"""SQLite persistence layer for conversations and messages."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import aiosqlite

from backend.config import get_settings

log = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None

_SCHEMA_VERSION = 3

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
        await _db.commit()
    else:
        version = row[0]
        if version < 2:
            await _db.executescript(_SCHEMA_V2)
            version = 2
        if version < 3:
            await _migrate_v3(_db)
            version = 3
        if version != _SCHEMA_VERSION:
            await _db.execute(
                "UPDATE schema_version SET version = ?", (_SCHEMA_VERSION,)
            )
            await _db.commit()
            log.info("Migrated database schema to v%d", _SCHEMA_VERSION)


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

async def list_conversations() -> list[dict]:
    db = _get_db()
    cur = await db.execute(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at,
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
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"],
        }
        for r in rows
    ]


async def get_conversation(conv_id: str) -> dict | None:
    db = _get_db()
    cur = await db.execute(
        "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
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
        "messages": messages,
        "created_at": conv["created_at"],
        "updated_at": conv["updated_at"],
    }


async def create_conversation(conv_id: str, title: str) -> dict:
    db = _get_db()
    now = _now_ms()
    await db.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, title, now, now),
    )
    await db.commit()
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


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


async def delete_conversation(conv_id: str) -> bool:
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
    cur = await conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    await conn.commit()
    return cur.rowcount > 0


async def clear_all_conversations() -> None:
    conn = _get_db()
    try:
        import shutil
        settings = get_settings()
        if settings.upload_dir.is_dir():
            shutil.rmtree(settings.upload_dir)
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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
# Bulk import (localStorage migration)
# ---------------------------------------------------------------------------

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
) -> None:
    db = _get_db()
    await db.execute(
        """
        INSERT OR IGNORE INTO request_logs
          (request_group, conversation_id, user_message, intent, community_area,
           community_area_name, sources, total_duration_ms, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_group, conversation_id, user_message, intent,
            community_area, community_area_name,
            json.dumps(sources) if sources else None,
            total_duration_ms, status, error_message, _now_ms(),
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


async def import_conversations(conversations: list[dict]) -> int:
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
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv["id"], conv.get("title", "Imported"), conv.get("createdAt", _now_ms()), conv.get("updatedAt", _now_ms())),
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
