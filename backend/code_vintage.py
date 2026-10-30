"""How current the indexed Municipal Code is (written at ingestion; see
ingestion/code_vintage.py). The code is a snapshot: a Council amendment after
``current_through`` is not in it, and the product must not imply otherwise."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

VINTAGE_FILE = Path(__file__).resolve().parent / "code_vintage.json"

# What users, chat and the API see. The rest of the file (ingested_at, chunk_count,
# collection, export_sha256) is ingestion bookkeeping for ops checks.
PUBLIC_FIELDS = ("current_through", "label", "source")


@lru_cache(maxsize=1)
def get_code_vintage_record() -> dict | None:
    """The whole vintage file, or None when it is missing/unreadable."""
    try:
        data = json.loads(VINTAGE_FILE.read_text())
        if isinstance(data, dict) and data.get("current_through"):
            return data
    except (OSError, ValueError):
        log.warning("Code vintage file unreadable: %s", VINTAGE_FILE)
    return None


def get_code_vintage() -> dict | None:
    """{"current_through": "2026-03-18", "label": "Council Journal of March 18, 2026",
    "source": ...} or None when the file is missing/unreadable (stamp omitted, not faked)."""
    record = get_code_vintage_record()
    if record is None:
        return None
    return {k: record[k] for k in PUBLIC_FIELDS if k in record}
