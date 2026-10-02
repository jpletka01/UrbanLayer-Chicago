"""Cut one subsection (and its table) out of an indexed Municipal Code article.

The code is indexed one ARTICLE per record (``17-2-0300``, "Bulk and density
standards", is ~32,000 characters) with its tables appended as ``[TABLE]`` blocks
after the paragraphs. A Profile number cites a SUBSECTION (``17-2-0304-A``), so the
source viewer needs just that subsection and the table it refers to, not the article.
"""

from __future__ import annotations

import re

SECTION_ID_RE = re.compile(r"^\d{1,2}-\d{1,3}-\d{3,4}(?:-[A-Z])?$")
_HEADING_RE = re.compile(r"^(\d{1,2}-\d{1,3}-\d{3,4}(?:-[A-Z])?)\s")
_BASE_RE = re.compile(r"^(\d{1,2}-\d{1,3}-)(\d{4})(?:-[A-Z])?$")

# Which table (by its column header) a subsection's standard lives in. (include, exclude):
# a table matches when its "Columns:" line contains every ``include`` substring and none
# of ``exclude``. Pinned to the ingested code's real table headers in tests.
TABLE_HINTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "17-2-0304-A": (("Maximum Floor Area Ratio",), ()),
    "17-2-0311-A": (("Maximum Building Height",), ()),
    "17-2-0303-A": (("Minimum Lot Area per Unit",), ()),
    "17-3-0403-A": (("Maximum Floor Area Ratio",), ("Proportion",)),
    "17-3-0408-A": (("Maximum Building Height",), ()),
    "17-3-0402-A": (("Minimum Lot Area per Unit",), ("Proportion",)),
    "17-4-0405-A": (("Maximum Base Floor Area Ratio",), ()),
    "17-4-0404-A": (("Minimum Lot Area per Unit",), ("Proportion",)),
    "17-5-0404": (("Maximum Floor Area Ratio",), ()),
}


def article_id(section_id: str) -> str:
    """The indexed article holding a section: 17-2-0304-A -> 17-2-0300. Ids without a
    four-digit part (2-120-740) are indexed as themselves."""
    m = _BASE_RE.match(section_id)
    if not m:
        return section_id
    return f"{m.group(1)}{int(m.group(2)) // 100 * 100:04d}"


def _is_descendant(heading_id: str, target: str) -> bool:
    return heading_id == target or heading_id.startswith(target + "-")


def extract_subsection(article_text: str, section_id: str) -> dict | None:
    """{"heading", "paragraphs", "tables"} for ``section_id`` inside an article's text,
    or None when the heading isn't there. Tables are returned as their raw
    ``Columns:`` / ``Row n:`` text, filtered to the table(s) this subsection cites."""
    body, *table_blocks = re.split(r"\n\[TABLE\]\n", article_text)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]

    start = next((i for i, p in enumerate(paragraphs) if (m := _HEADING_RE.match(p)) and m.group(1) == section_id), None)
    if start is None:
        return None
    picked = [paragraphs[start]]
    for p in paragraphs[start + 1:]:
        m = _HEADING_RE.match(p)
        if m and not _is_descendant(m.group(1), section_id):
            break
        picked.append(p)

    # A long table is indexed as several [TABLE] blocks sharing one header (row batches);
    # put those back together so the viewer shows each table whole.
    merged: dict[str, list[str]] = {}
    include, exclude = TABLE_HINTS.get(section_id, ((), ()))
    if include:
        for block in table_blocks:
            columns, _, rows = block.strip().split("\n\n", 1)[0].strip().partition("\n")
            if all(s in columns for s in include) and not any(s in columns for s in exclude):
                merged.setdefault(columns, []).append(rows)
    tables = [columns + "\n" + "\n".join(r for r in rows if r) for columns, rows in merged.items()]
    title = _HEADING_RE.sub("", picked[0], count=1)
    heading = title.split(". ")[0].rstrip(".").strip()[:80]
    return {"heading": heading, "paragraphs": picked, "tables": tables}
