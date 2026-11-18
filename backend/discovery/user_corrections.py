"""Reviewed user reports of a lot's building (decision Item 129 §4): the committed file's shape and how to read it.

``user_corrections.json`` beside this module is written by the /admin queue's export (a person reviewed every entry)
and changed only in a PR. Keyed by PIN10: ``{stories, empty, reviewed, report_ids, what}``, exactly one of a story
count (1-150) or ``empty: true``. Kept free of heavy imports: ``lot_facts`` applies it on each index build and the
data-health checker validates it (``internal.user_corrections``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

USER_CORRECTIONS_FILE = Path(__file__).with_name("user_corrections.json")
USER_REPORT_SOURCE = "user_report_reviewed"
MAX_USER_STORIES = 150
# Past this many entries the review queue has outgrown one person (Item 129 §5: weigh reporters then); data health warns.
MAX_ENTRIES = 2_000


def validate_user_correction(pin10: str, entry: Any) -> str | None:
    """Why an entry can't be applied, or None when it is sound. Shape: ``{stories, empty, reviewed, report_ids, what}``
    keyed by PIN10; exactly one of a story count (1-150) or ``empty: true``."""
    if not (isinstance(pin10, str) and len(pin10) == 10 and pin10.isdigit()):
        return "key is not a 10-digit PIN"
    if not isinstance(entry, dict):
        return "entry is not an object"
    stories, empty = entry.get("stories"), entry.get("empty")
    if empty is True:
        if stories is not None:
            return "both a story count and empty"
    elif not (isinstance(stories, int) and not isinstance(stories, bool) and 1 <= stories <= MAX_USER_STORIES):
        return "needs stories 1-150 or empty: true"
    reviewed = entry.get("reviewed")
    if not (isinstance(reviewed, str) and len(reviewed) == 10 and reviewed[4] == "-" and reviewed[7] == "-"):
        return "reviewed is not a YYYY-MM-DD day"
    ids = entry.get("report_ids")
    if not (isinstance(ids, list) and ids and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)):
        return "report_ids is not a non-empty list of report ids"
    return None


def load_user_corrections(path: Path = USER_CORRECTIONS_FILE) -> dict[str, dict[str, Any]]:
    """The sound entries of the committed file (an unsound one is skipped here and alarmed by data health); none when
    there is no file yet."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_") and validate_user_correction(k, v) is None}


def read_raw(path: Path = USER_CORRECTIONS_FILE) -> dict[str, Any] | None:
    """The file as written (None when there is none yet), for the data-health check."""
    if not path.exists():
        return None
    return json.loads(path.read_text())
