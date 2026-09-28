"""Check that an answer's citation markers point at context it was actually given.

The synthesizer cites municipal code as ``[N]`` (1-based index into the turn's
code chunks) and API data as ``[data:<source>]``. Nothing used to verify them:
the chat UI silently drops a ``[7]`` when only five chunks were retrieved, so a
fabricated citation was invisible to users and to us. This module is the single
check, used by the chat stream (logged, and reported on the ``done`` event) and
by the eval harness.
"""

from __future__ import annotations

import re
from typing import Any

# Context field -> the marker name the synthesizer prompt tells the model to use.
DATA_SOURCE_FIELDS: dict[str, str] = {
    "crime_last_90d": "crime",
    "open_311_requests": "311",
    "permits": "permits",
    "violations": "violations",
    "businesses": "business",
    "vacant_buildings": "vacant_buildings",
    "food_inspections": "food_inspections",
}
KNOWN_DATA_MARKERS = frozenset(DATA_SOURCE_FIELDS.values())

_CODE_REF = re.compile(r"\[(\d+)\]")
_DATA_REF = re.compile(r"\[data:([^\]\s]+)\]")


def data_sources_present(context: Any) -> set[str]:
    """Marker names for the data sources that are populated in a context
    (a ContextObject or its dict form)."""
    get = context.get if isinstance(context, dict) else (lambda k: getattr(context, k, None))
    return {marker for field, marker in DATA_SOURCE_FIELDS.items() if get(field)}


def citation_problems(answer: str, num_code_chunks: int, data_present: set[str]) -> list[str]:
    """Human-readable problems with the answer's citations; empty when all are backed."""
    problems: list[str] = []
    for ref in sorted({int(n) for n in _CODE_REF.findall(answer)}):
        if not 1 <= ref <= num_code_chunks:
            problems.append(f"[{ref}] cites a code chunk that wasn't retrieved ({num_code_chunks} available)")
    for marker in sorted(set(_DATA_REF.findall(answer))):
        if marker not in KNOWN_DATA_MARKERS:
            problems.append(f"[data:{marker}] is not a known data source")
        elif marker not in data_present:
            problems.append(f"[data:{marker}] cited but that data wasn't in the context")
    return problems
