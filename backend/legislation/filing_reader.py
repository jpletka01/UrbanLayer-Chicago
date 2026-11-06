"""Offline-only candidate selection for WS2 PR4's filing-reader evaluation panel.

This is deliberately not part of the serving path.  It selects current Type 1
zoning matters from Clerk *metadata* so an operator can review a proposed PDF
download manifest before any public document is fetched.  PDF retrieval, OCR,
and parsing belong in a later explicitly invoked development-only tool.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from typing import Iterable

import httpx

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
    download_bytes: int | None = None


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


async def build_download_manifest(*, limit: int = 30) -> list[SampleCandidate]:
    """Read Clerk metadata until ``limit`` eligible documents are found; fetches no PDFs."""
    selected: list[SampleCandidate] = []
    matters = await clerk.pending_zoning_matters()
    for listed in sorted((m for m in matters if is_type_1(m)), key=lambda m: m.record_number, reverse=True):
        detail = await clerk.get_matter(listed.matter_id)
        if detail is None:
            continue
        selected.extend(sample_candidates([detail], limit=1))
        if len(selected) == limit:
            return selected
    return selected


async def add_head_sizes(rows: Iterable[SampleCandidate]) -> list[SampleCandidate]:
    """Add Content-Length metadata without requesting attachment bodies.

    Missing or malformed lengths stay ``None``: an operator must not approve a
    download budget whose size the public host did not disclose.
    """
    out: list[SampleCandidate] = []
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for row in rows:
            try:
                response = await client.head(row.url)
                value = response.headers.get("Content-Length") if response.is_success else None
                size = int(value) if value and value.isdigit() else None
            except httpx.HTTPError:
                size = None
            out.append(SampleCandidate(**{**row.__dict__, "download_bytes": size}))
    return out


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Print a WS2 PR4 PDF approval manifest without downloading PDFs")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--head-sizes", action="store_true", help="also make HEAD-only size requests")
    args = parser.parse_args(argv)
    try:
        rows = await build_download_manifest(limit=args.limit)
    except (clerk.ClerkUnavailable, clerk.ClerkQueryError, ValueError) as exc:
        print(f"filing reader manifest: failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.head_sizes:
        rows = await add_head_sizes(rows)
    print(json.dumps({"files": [row.__dict__ for row in rows], "total_bytes": sum(
        row.download_bytes or 0 for row in rows), "unknown_sizes": sum(row.download_bytes is None for row in rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
