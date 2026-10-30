"""Which passed code amendments matter to the product, and which sections they touch.

Pure functions over Clerk titles and section ids; no network. Shared by the daily
sync (classifying the live list) and ``currency`` (matching amendments to the sections
a page or an answer cites).

Relevance classes:

- ``title17``: the title names Title 17 or a 17-x section (the M1 rule; exactly the 16
  passed after 2026-03-18, including the omnibus).
- ``cited_other``: outside Title 17 but touching a section the product cites or chat
  routinely retrieves (:data:`CITED_PREFIXES`).
- ``other``: everything else (liquor moratoria, parking meters, procurement, ...).
"""

from __future__ import annotations

import re

from backend.code_sections import article_id
from backend.retrieval.clerk import ClerkMatter, title17_amendment, touches_title17

# Non-Title-17 sections the product cites or chat answers from (plan §1.1), by prefix on
# a segment boundary. Title 14 (building code, incl. the CHRS demolition hold 14A-4-407.6),
# Chapter 2-44 (housing), the property-tax incentive revocation section 2-45-165, the
# landmarks chapter 2-120, and Chapter 18-14 (energy and water benchmarking).
CITED_PREFIXES = ("14A", "14B", "14F", "14G", "14M", "14N", "14R", "14X", "2-44", "2-45-165", "2-120", "18-14")

# Any Municipal Code section id in a title: 17-3-0503-D, 14X-8-802.2.2, 2-44-170, 17-9.
_ANY_SECTION_RE = re.compile(r"\b\d{1,2}[A-Z]?-\d+(?:-[\dA-Z]+(?:\.\d+)*(?:-[A-Z])?)?\b")
# "17-9-0109A" is how Council titles write subsection A of 17-9-0109.
_GLUED_LETTER_RE = re.compile(r"^(\d{1,2}-\d{1,3}-\d{4})([A-Z])$")
_FOUR_DIGIT_RE = re.compile(r"^\d{1,2}-\d{1,3}-\d{4}$")


def normalize_section(section: str) -> str:
    s = section.strip().upper().lstrip("§").strip()
    m = _GLUED_LETTER_RE.match(s)
    return f"{m.group(1)}-{m.group(2)}" if m else s


# Title 14 (the building code, IBC-style numbering) writes subsections with dots:
# 14X-8-802.2.2 is inside 14X-8-802, and the corpus indexes it under 14X-8-802. In
# Title 17 a dot is a separate section (17-9-0129.1 is not inside 17-9-0129).
_DOTTED_SUBSECTIONS_RE = re.compile(r"^14[A-Z]-")


def _within(child: str, parent: str) -> bool:
    if child == parent or child.startswith(parent + "-"):
        return True
    return bool(_DOTTED_SUBSECTIONS_RE.match(parent)) and child.startswith(parent + ".")


def _is_article(section: str) -> bool:
    """An id the code index holds a whole article under: 17-3-0500, and in chapter 17-7
    also 17-7-0570 (see :func:`backend.code_sections.article_id`)."""
    return bool(_FOUR_DIGIT_RE.match(section)) and article_id(section) == section


def sections_overlap(a: str, b: str) -> bool:
    """True when two section ids name the same text or one contains the other:
    17-3-0503-D ⇄ 17-3-0503 (subsection), 17-9 ⇄ 17-9-0109 (chapter), and an indexed
    article ⇄ any section in it (17-3-0500 ⇄ 17-3-0503-D, 17-7-0570 ⇄ 17-7-0574). Siblings (17-3-0503-A vs -D)
    and decimal neighbours (17-9-0129 vs 17-9-0129.1, a separate section) don't overlap."""
    a, b = normalize_section(a), normalize_section(b)
    if _within(a, b) or _within(b, a):
        return True
    return (_is_article(a) and article_id(b) == a) or (_is_article(b) and article_id(a) == b)


def sections_in_title(title: str) -> list[str]:
    """Section ids named in a title, most specific only: "Chapter 17-3 by adding Section
    17-3-0600" yields just 17-3-0600 (the chapter is where the new section goes, not
    what changed)."""
    found = list(dict.fromkeys(normalize_section(s) for s in _ANY_SECTION_RE.findall(title)))
    return [s for s in found if not any(o != s and _within(o, s) for o in found)]


def cites_other(sections: list[str]) -> bool:
    return any(_within(s, p) for s in sections for p in CITED_PREFIXES)


def relevance(title: str) -> str:
    if touches_title17(title):
        return "title17"
    return "cited_other" if cites_other(sections_in_title(title)) else "other"


def live_record(m: ClerkMatter) -> dict:
    """One passed matter as the snapshot stores it (plan §5.1)."""
    rel = relevance(m.title)
    kind = title17_amendment(m).kind if rel == "title17" else "text"
    return {
        "record": m.record_number,
        "matter_id": m.matter_id,
        "url": m.url,
        "title": re.sub(r"\s+", " ", m.title).strip(),
        "passed_on": m.passed_on.isoformat() if m.passed_on else None,
        "category": m.category,
        "relevance": rel,
        "kind": kind,
        "sections": sections_in_title(m.title),
    }
