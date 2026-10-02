"""Record how current the ingested Municipal Code is.

The American Legal export opens with "Current through Council Journal of March 18,
2026". Any Council amendment after that date is NOT in the indexed text, so the
Profile and chat state it ("Municipal Code current through ...") instead of letting
the code read as if it were live. The date is written to ``backend/code_vintage.json``
(tracked and shipped with ``backend/``) whenever the code is re-parsed.

    python -m ingestion.code_vintage            # re-read the export header
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

SOURCE_FILE = Path(__file__).resolve().parent.parent / "chicago-il-codes.html"
VINTAGE_FILE = Path(__file__).resolve().parent.parent / "backend" / "code_vintage.json"

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


def write_code_vintage(source: Path = SOURCE_FILE, out: Path = VINTAGE_FILE) -> dict:
    """Read the header of the export and write the vintage file. Raises if absent."""
    with source.open(encoding="utf-8") as f:
        head = f.read(20_000)
    vintage = extract_code_vintage(head)
    if vintage is None:
        raise ValueError(f"No 'Current through Council Journal of ...' header in {source}")
    out.write_text(json.dumps(vintage, indent=2) + "\n")
    return vintage


if __name__ == "__main__":
    print(json.dumps(write_code_vintage(Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE_FILE), indent=2))
