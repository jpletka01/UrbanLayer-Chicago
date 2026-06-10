"""Check whether the municipal code source HTML has changed since last ingestion.

Usage:
    python -m ingestion.source_check
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path


log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
SOURCE_HTML = DATA_DIR / "chicago-il-codes.html"
SOURCE_HASH_FILE = DATA_DIR / "source_hash.json"


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check() -> dict:
    if not SOURCE_HTML.exists():
        return {"status": "missing", "message": f"Source file not found: {SOURCE_HTML}"}

    current_hash = _file_hash(SOURCE_HTML)

    if not SOURCE_HASH_FILE.exists():
        return {
            "status": "unknown",
            "message": "No previous hash recorded. Run `python -m ingestion.update --manifest` first.",
            "current_hash": current_hash,
        }

    saved = json.loads(SOURCE_HASH_FILE.read_text())
    saved_hash = saved.get("hash", "")

    if current_hash == saved_hash:
        return {"status": "unchanged", "message": "Source HTML has not changed since last ingestion."}

    return {
        "status": "updated",
        "message": "Source HTML has changed -- run `python -m ingestion.update` to re-ingest.",
        "previous_hash": saved_hash,
        "current_hash": current_hash,
    }


def save_hash() -> None:
    if not SOURCE_HTML.exists():
        return
    data = {"hash": _file_hash(SOURCE_HTML)}
    SOURCE_HASH_FILE.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = check()
    log.info("%s: %s", result["status"].upper(), result["message"])


if __name__ == "__main__":
    main()
