"""Offline-only candidate selection for WS2 PR4's filing-reader evaluation panel.

This is deliberately not part of the serving path.  It selects current Type 1
zoning matters from Clerk *metadata* so an operator can review a proposed PDF
download manifest before any public document is fetched.  PDF retrieval, OCR,
and parsing belong in a later explicitly invoked development-only tool.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx
from pypdf import PdfReader

from backend.legislation.pending import attachment_allowed
from backend.retrieval import clerk


_TYPE_1 = re.compile(r"\b(?:APP(?:LICATION)?\s*(?:NO\.?\s*)?)?\d{4,}T1\b", re.IGNORECASE)
MAX_SAMPLE_FILE_BYTES = 8 * 1024 * 1024
_EDS_PAGE = re.compile(r"\b(?:EDS|ECONOMIC\s+DISCLOS(?:URE|URE\s+STATEMENT))\b", re.IGNORECASE)
_LABELED_FIELDS = {
    "lot_area": re.compile(r"\b(?:lot\s+area)\s*[:\-]\s*([\d,]+)\s*(sq\.?\s*ft\.?)", re.IGNORECASE),
    "dwelling_units": re.compile(r"\b(?:dwelling\s+units?)\s*[:\-]\s*([\d,]+)\b", re.IGNORECASE),
    "height": re.compile(r"\b(?:height)\s*[:\-]\s*([\d,.]+)\s*(ft\.?)", re.IGNORECASE),
    "far": re.compile(r"\b(?:floor\s+area\s+ratio|FAR)\s*[:\-]\s*([\d.]+)\b", re.IGNORECASE),
    "parking": re.compile(r"\b(?:parking(?:\s+spaces?)?)\s*[:\-]\s*([\d,]+)\b", re.IGNORECASE),
}


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


@dataclass(frozen=True)
class ParsedField:
    id: str
    value: str
    unit: str | None = None


def parse_labeled_type1_text(text: str) -> list[ParsedField]:
    """Extract only explicitly labelled Type 1 values from one already-safe page.

    This deliberately performs no arithmetic, column guessing, or inference.
    Duplicate labels are ambiguous and therefore withheld.
    """
    found: list[ParsedField] = []
    for field_id, pattern in _LABELED_FIELDS.items():
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            continue
        match = matches[0]
        found.append(ParsedField(field_id, match.group(1).replace(",", ""), match.group(2) if match.lastindex == 2 else None))
    return found


def classify_page_text(text: str) -> str:
    """A missing or uncertain OCR result is never eligible for extraction."""
    if _EDS_PAGE.search(text):
        return "eds"
    return "safe" if len(text.strip()) >= 20 else "unreadable"


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


async def download_sample(rows: Iterable[SampleCandidate], destination: Path) -> list[dict]:
    """Download approved public PDFs outside Git with bounded, validated writes.

    This is development-only: no serving import calls it.  A later page reader
    must remove EDS pages before producing any retained text or review artifact.
    """
    destination.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for row in rows:
            path = destination / f"{row.record_number}.pdf"
            partial = path.with_suffix(".pdf.part")
            digest = hashlib.sha256()
            total = 0
            try:
                async with client.stream("GET", row.url) as response:
                    response.raise_for_status()
                    declared = response.headers.get("Content-Length")
                    if declared and declared.isdigit() and int(declared) > MAX_SAMPLE_FILE_BYTES:
                        raise ValueError(f"{row.record_number}: declared size exceeds cap")
                    content_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
                    # Clerk's Azure blob host returns application/octet-stream for
                    # some perfectly valid PDFs. The magic-byte check below remains
                    # mandatory, so accepting this generic type does not trust it.
                    if content_type not in {"application/pdf", "application/octet-stream"}:
                        raise ValueError(f"{row.record_number}: response is not a PDF")
                    with partial.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > MAX_SAMPLE_FILE_BYTES:
                                raise ValueError(f"{row.record_number}: received size exceeds cap")
                            digest.update(chunk)
                            output.write(chunk)
                if partial.read_bytes()[:5] != b"%PDF-":
                    raise ValueError(f"{row.record_number}: PDF signature missing")
                screened = screen_scanned_pages_for_eds(partial, screen_pages_for_eds(partial))
                if not screened or any(page.status != "safe" for page in screened):
                    raise ValueError(f"{row.record_number}: EDS or unreadable page; refusing to retain packet")
                partial.replace(path)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            saved.append({"record_number": row.record_number, "file_name": row.file_name,
                          "bytes": total, "sha256": digest.hexdigest()})
    return saved


@dataclass(frozen=True)
class PageScreen:
    page: int
    status: str  # safe | eds | unreadable


def screen_pages_for_eds(path: Path) -> list[PageScreen]:
    """Classify each PDF page without persisting its text.

    A native-text EDS page is quarantined. An image-only or unreadable page is
    not safe and must be manually screened before any future OCR pass. The
    function returns no text, so EDS content cannot enter fixtures or artifacts.
    """
    reader = PdfReader(path)
    pages: list[PageScreen] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # malformed individual page; fail closed
            pages.append(PageScreen(number, "unreadable"))
            continue
        if not text.strip():
            pages.append(PageScreen(number, "unreadable"))
        else:
            pages.append(PageScreen(number, classify_page_text(text)))
    return pages


def screen_scanned_pages_for_eds(path: Path, pages: Iterable[PageScreen]) -> list[PageScreen]:
    """OCR only unreadable pages in memory and retain classifications, never text."""
    out: list[PageScreen] = []
    for result in pages:
        if result.status != "unreadable":
            out.append(result)
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="urbanlayer-filing-") as directory:
                prefix = Path(directory) / "page"
                subprocess.run(
                    ["pdftoppm", "-f", str(result.page), "-l", str(result.page), "-r", "200", "-png", "-singlefile", str(path), str(prefix)],
                    check=True, capture_output=True,
                )
                text = subprocess.run(
                    ["tesseract", "stdin", "stdout"], input=prefix.with_suffix(".png").read_bytes(),
                    check=True, capture_output=True,
                ).stdout.decode("utf-8")
        except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
            out.append(result)
            continue
        out.append(PageScreen(result.page, classify_page_text(text)))
    return out


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Print a WS2 PR4 PDF approval manifest without downloading PDFs")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--head-sizes", action="store_true", help="also make HEAD-only size requests")
    parser.add_argument("--download-dir", type=Path, help="development-only private PDF destination")
    parser.add_argument("--screen-dir", type=Path, help="screen existing private PDFs for EDS pages")
    parser.add_argument("--screen-limit", type=int, help="bound the number of private PDFs screened per run")
    parser.add_argument("--screen-offset", type=int, default=0, help="skip this many private PDFs before screening")
    args = parser.parse_args(argv)
    if args.screen_dir:
        if args.screen_offset < 0:
            parser.error("--screen-offset must be non-negative")
        pdfs = sorted(args.screen_dir.glob("*.pdf"))[args.screen_offset:]
        if args.screen_limit is not None:
            pdfs = pdfs[:args.screen_limit]
        screened = {
            pdf.name: [page.__dict__ for page in screen_scanned_pages_for_eds(pdf, screen_pages_for_eds(pdf))]
            for pdf in pdfs
        }
        print(json.dumps(screened, indent=2))
        return 0
    try:
        rows = await build_download_manifest(limit=args.limit)
    except (clerk.ClerkUnavailable, clerk.ClerkQueryError, ValueError) as exc:
        print(f"filing reader manifest: failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.head_sizes:
        rows = await add_head_sizes(rows)
    if args.download_dir:
        saved = await download_sample(rows, args.download_dir)
        print(json.dumps({"downloaded": saved}, indent=2))
        return 0
    print(json.dumps({"files": [row.__dict__ for row in rows], "total_bytes": sum(
        row.download_bytes or 0 for row in rows), "unknown_sizes": sum(row.download_bytes is None for row in rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
