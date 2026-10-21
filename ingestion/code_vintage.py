"""Record how current the ingested Municipal Code is.

The American Legal export opens with "Current through Council Journal of March 18,
2026". Any Council amendment after that date is NOT in the indexed text, so the
Profile and chat state it ("Municipal Code current through ...") instead of letting
the code read as if it were live. The date is written to ``backend/code_vintage.json``
(tracked and shipped with ``backend/``) by ``ingestion.update``, only after the new text
is in Qdrant, together with what was ingested: when, how many chunks, which collection,
and the export's sha256. A parse or a dry run never writes it.

    python -m ingestion.code_vintage [export.html]   # print an export's header; writes nothing
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_FILE = Path(__file__).resolve().parent.parent / "chicago-il-codes.html"
VINTAGE_FILE = Path(__file__).resolve().parent.parent / "backend" / "code_vintage.json"

# The app reads the code through this alias; each vintage is its own collection behind it.
CODE_ALIAS = "municipal_code"

_HEADER_RE = re.compile(r"Current through\s+(Council Journal of\s+([A-Z][a-z]+ \d{1,2}, \d{4}))")


def extract_code_vintage(html_head: str) -> dict | None:
    """Parse the export's 'Current through ...' line; None if it isn't there."""
    m = _HEADER_RE.search(html_head)
    if not m:
        return None
    try:
        through = datetime.strptime(m.group(2), "%B %d, %Y").date()
    except ValueError:
        return None
    return {
        "current_through": through.isoformat(),
        "label": m.group(1),
        "source": "Municipal Code of Chicago, American Legal export",
    }


def read_export_vintage(source: Path = SOURCE_FILE) -> dict:
    """The export's header vintage. Raises if the header is absent."""
    with source.open(encoding="utf-8") as f:
        head = f.read(20_000)
    vintage = extract_code_vintage(head)
    if vintage is None:
        raise ValueError(f"No 'Current through Council Journal of ...' header in {source}")
    return vintage


def collection_for(current_through: str) -> str:
    """The Qdrant collection that holds one vintage, e.g. municipal_code_2026-03-18."""
    return f"{CODE_ALIAS}_{current_through}"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_code_vintage(path: Path = VINTAGE_FILE) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_code_vintage(
    source: Path,
    *,
    chunk_count: int,
    collection: str,
    out: Path = VINTAGE_FILE,
    ingested_at: datetime | None = None,
) -> dict:
    """Write the vintage file for an export that is now in ``collection``."""
    vintage = read_export_vintage(source)
    vintage.update(
        ingested_at=(ingested_at or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        chunk_count=chunk_count,
        collection=collection,
        export_sha256=file_sha256(source),
    )
    out.write_text(json.dumps(vintage, indent=2) + "\n")
    return vintage


if __name__ == "__main__":
    print(json.dumps(read_export_vintage(Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE_FILE), indent=2))
