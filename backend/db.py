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

_SCHEMA_VERSION = 1

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
        await _db.commit()


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
        "SELECT role, content, context_json, plan_json, map_data_json, map_fetched_at "
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
               map_data_json, map_fetched_at, position, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                msg["role"],
                msg["content"],
                json.dumps(msg["context"]) if msg.get("context") else None,
                json.dumps(msg["plan"]) if msg.get("plan") else None,
                json.dumps(msg["map_data"]) if msg.get("map_data") else None,
                msg.get("map_fetched_at"),
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
    db = _get_db()
    cur = await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    await db.commit()
    return cur.rowcount > 0


async def clear_all_conversations() -> None:
    db = _get_db()
    await db.execute("DELETE FROM conversations")
    await db.commit()


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
