"""Offline-only candidate selection for WS2 PR4's filing-reader evaluation panel.

This is deliberately not part of the serving path.  It selects current Type 1
zoning matters from Clerk *metadata* so an operator can review a proposed PDF
download manifest before any public document is fetched.  PDF retrieval, OCR,
and parsing belong in a later explicitly invoked development-only tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from backend.legislation.pending import attachment_allowed
from backend.retrieval import clerk


_TYPE_1 = re.compile(r"\b(?:APP(?:LICATION)?\s*(?:NO\.?\s*)?)?\d{4,}T1\b", re.IGNORECASE)


def is_type_1(matter: clerk.ClerkMatter) -> bool:
    """A conservative title-level candidate screen, never an extraction assertion."""
    return matter.category.startswith(clerk.ZONING_RECLASSIFICATIONS) and bool(_TYPE_1.search(matter.title))


def eligible_attachments(matter: clerk.ClerkMatter) -> tuple[clerk.ClerkAttachment, ...]:
    """Public PDF metadata allowed into a *review manifest*.

    Filename/type screening is intentionally not treated as proof that a bundled
    PDF has no Economic Disclosure Statement pages; the later page reader must
    still detect and discard those pages before retaining any OCR text.
    """
    return tuple(
        attachment for attachment in matter.attachments
        if attachment_allowed(attachment) and attachment.file_name.lower().endswith(".pdf")
    )


@dataclass(frozen=True)
class SampleCandidate:
    matter_id: str
    record_number: str
    title: str
    file_name: str
    url: str
    attachment_type: str


def sample_candidates(matters: Iterable[clerk.ClerkMatter], *, limit: int = 30) -> list[SampleCandidate]:
    """One deterministic, metadata-only candidate per matter, newest record first.

    A document is not selected merely because it is a PDF: it must survive the
    existing allowlist/EDS metadata check.  The caller presents this list (and
    HEAD-derived total size) for approval before downloading anything.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    rows: list[SampleCandidate] = []
    for matter in sorted(matters, key=lambda m: m.record_number, reverse=True):
        if not is_type_1(matter):
            continue
        attachments = eligible_attachments(matter)
        if not attachments:
            continue
        attachment = attachments[0]
        rows.append(SampleCandidate(
            matter_id=matter.matter_id, record_number=matter.record_number, title=matter.title,
            file_name=attachment.file_name, url=attachment.url, attachment_type=attachment.type,
        ))
        if len(rows) == limit:
            break
    return rows
