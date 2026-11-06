"""Offline-only deterministic reader for WS2 PR4's Type 1 filing evaluation panel.

This is deliberately not part of the serving path, and the production image has
neither ``pypdf`` nor Poppler/Tesseract.  It:

1. selects current Type 1 zoning matters from Clerk *metadata*;
2. keeps exactly two attachment roles per matter, the ``Legislation`` ordinance
   and the ``Exhibits`` "Narrative and Plans" packet.  The ``Application``
   (owner/applicant/attorney identity, sometimes a bundled EDS) and the EDS
   are never selected, so they are never downloaded;
3. downloads a selected PDF privately with size/type/signature checks and
   refuses to retain a packet with any EDS-looking or unreadable page;
4. classifies each page by positive type (``ordinance`` / ``narrative``) and
   parses only those pages, with exact labelled patterns and no arithmetic.

Every emitted value is a *draft* for a human reviewer, never a published fact.
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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import httpx

from backend.legislation import address_titles
from backend.legislation.ordinance_reader import normalize_district
from backend.legislation.pending import attachment_allowed
from backend.retrieval import clerk


READER_VERSION = "ws2-pr4a-4"
_TYPE_1 = re.compile(r"\b(?:APP(?:LICATION)?\s*(?:NO\.?\s*)?)?\d{4,}T1\b", re.IGNORECASE)
MAX_SAMPLE_FILE_BYTES = 8 * 1024 * 1024

# Attachment roles: (Clerk attachment type, file-name word).  Anything else is
# not read.  The Application form names owners and attorneys and has been seen
# bundling an EDS page, so it is excluded by role rather than screened.
ROLES = {"ordinance": ("Legislation", "ordinance"), "narrative": ("Exhibits", "narrative")}

# EDS (Economic Disclosure Statement and Affidavit) markers.  Over-matching is
# acceptable: a hit rejects the whole packet, it never selects one.
_EDS_PAGE = re.compile(
    r"\bEDS\b|ECONOMIC\s+DISCLOS|DISCLOSING\s+PART(?:Y|IES)|DISCLOSURE\s+OF\s+RETAINED"
    r"|FAMILIAL\s+RELATIONSHIP|BENEFICIAL\s+(?:OWNER|INTEREST)|AFFIDAVIT\s+OF\s+(?:THE\s+)?DISCLOS",
    re.IGNORECASE,
)
_ORDINANCE_PAGE = re.compile(r"ORDAIN.{0,600}?Title\s+17|Title\s+17.{0,200}?Chicago\s+Zoning\s+Ordinance",
                             re.IGNORECASE | re.DOTALL)
_NARRATIVE_PAGE = re.compile(r"\bLot\s+Area\b", re.IGNORECASE)

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)?(?:\.(\d+))?"
# A zone class as printed: B2-5, RS3, RM 4.5, C1-1, DX-12, or a planned development number.
# OCR reads a digit slot as l/I (1), S (5) or O (0) on these scans ("Cl-1", "RM-S"); _ocr_district maps them back.
_D = r"[\dlISO]"
_DISTRICT = (r"(?:(?:PD|PMD)\s?\d{1,4}[A-Z]?|[A-Z]{1,4}(?:" + _D + r"\s?-\s?|\s?-?\s?)" + _D + r"{1,2}(?:\.\d)?)"
             r"(?![\w.-])")
_SOURCE_SPAN = re.compile(r"changing\s+all\s+(?:of\s+)?the\s+(.{0,240}?)\bsymbols?\b", re.IGNORECASE | re.DOTALL)
_TARGET = re.compile(r"\b[Tt][Oo]\s+[Tt][Hh](?:OSE|ose|AT|at|E|e)\s+[Oo][Ff]\s+(?:[Aa][Nn]?\s+|[Tt][Hh][Ee]\s+)?(" + _DISTRICT + r")")
_DISTRICT_IN_SPAN = re.compile(_DISTRICT)
# A colon and/or a table border on the SAME line.  Crossing a line break let a list
# number ("1. Lot area") read as the FAR on the train split.
_SEP = r"[ \t]*(?:[:\-–][ \t]*)?(?:\|[ \t]*)?"
_APPROX = r"(?:approx(?:imately|\.)?\s*)?"
# Lot area may sit on the next line (two-column layouts); its required area unit keeps that safe.
_LOT_AREA = re.compile(r"\bLot\s+Area" + _SEP + r"(?:\n[ \t]*)?" + _APPROX + _NUM
                       + r"\s*(?:square\s+feet|sq\.?\s*f(?:ee)?t\.?|s\.?f\.?)(?![a-z])", re.IGNORECASE)
_FAR_LABEL = re.compile(r"(\b[A-Za-z]+[ \t]+)?(?:\b[Ff]loor\s+[Aa]rea\s+[Rr]atio|\bF\.?A\.?R\.?)(?:\s*\(FAR\))?"
                        + _SEP + _NUM + r"(?![\d,]|\s*(?:sq|square|s\.?f\b|%))")
_FAR_PAREN = re.compile(r"\((\d+)?\.?(\d+)?\s*F\.?A\.?R\.?\)")
_FAR_NOT_PROJECT = {"base", "maximum", "max", "allowed", "allowable", "permitted", "required"}
_COUNT_END = r"\b(?!-\d)"  # never a code section such as 17-10-0200
_UNITS = re.compile(r"\b(?:Dwelling\s+Units|Residential\s+Units|Number\s+of\s+(?:Dwelling\s+|Residential\s+)?Units)"
                    + _SEP + r"(\d+)" + _COUNT_END, re.IGNORECASE)
_EFFICIENCY = re.compile(r"\bEfficiency\s+Units?\s*[:\-]", re.IGNORECASE)
_HEIGHT = re.compile(r"\b(?:Building\s+)?Height" + _SEP + _APPROX + r"(\d+(?:\.\d+)?)\s*(?:feet|foot|ft\.?|['’°])",
                     re.IGNORECASE)
# Anything number-like right after the foot value is an inch part ("65'-1 ¼\"" OCRs as "65’-1 %”").
_INCHES = re.compile(r"\s*(?:and\s*)?-?\s*(\d+)([^\n]{0,6})")
_PARKING = re.compile(r"(\b[A-Za-z]+[ \t]+)?\bParking(?:\s+Spaces)?" + _SEP + r"(\d+|zero|none)" + _COUNT_END, re.IGNORECASE)
_PARKING_NOT_CARS = {"bicycle", "bicycles", "bike", "bikes"}


def is_type_1(matter: clerk.ClerkMatter) -> bool:
    """A conservative title-level candidate screen, never an extraction assertion."""
    return matter.category.startswith(clerk.ZONING_RECLASSIFICATIONS) and bool(_TYPE_1.search(matter.title))


def attachment_role(attachment: clerk.ClerkAttachment) -> str | None:
    if not attachment_allowed(attachment) or not attachment.file_name.lower().endswith(".pdf"):
        return None
    name = attachment.file_name.lower()
    for role, (kind, word) in ROLES.items():
        if attachment.type == kind and word in name and "application" not in name:
            return role
    return None


def role_attachments(matter: clerk.ClerkMatter) -> dict[str, clerk.ClerkAttachment]:
    """The single ordinance and narrative attachment; an ambiguous role is dropped."""
    found: dict[str, list[clerk.ClerkAttachment]] = {}
    for attachment in matter.attachments:
        role = attachment_role(attachment)
        if role:
            found.setdefault(role, []).append(attachment)
    return {role: rows[0] for role, rows in found.items() if len(rows) == 1}


@dataclass(frozen=True)
class SampleCandidate:
    matter_id: str
    record_number: str
    title: str
    role: str
    file_name: str
    url: str
    attachment_type: str
    download_bytes: int | None = None


@dataclass(frozen=True)
class ParsedField:
    id: str
    value: str
    unit: str | None = None
    page: int | None = None
    source: str | None = None  # attachment role


def sample_candidates(matters: Iterable[clerk.ClerkMatter], *, limit: int = 30) -> list[SampleCandidate]:
    """Up to ``limit`` matters (newest first) with both roles present; one row per role.

    A matter missing either the ordinance or the narrative is skipped so every
    panel row can be labelled for both district and project fields.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    rows: list[SampleCandidate] = []
    taken = 0
    for matter in sorted(matters, key=lambda m: m.record_number, reverse=True):
        if not is_type_1(matter):
            continue
        roles = role_attachments(matter)
        if set(roles) != set(ROLES):
            continue
        for role in ROLES:
            attachment = roles[role]
            rows.append(SampleCandidate(
                matter_id=matter.matter_id, record_number=matter.record_number, title=matter.title, role=role,
                file_name=attachment.file_name, url=attachment.url, attachment_type=attachment.type,
            ))
        taken += 1
        if taken == limit:
            break
    return rows


async def build_download_manifest(*, limit: int = 30, skip: Iterable[str] = ()) -> list[SampleCandidate]:
    """Read Clerk metadata until ``limit`` eligible matters are found; fetches no PDFs."""
    skipped = set(skip)
    selected: list[SampleCandidate] = []
    matters = await clerk.pending_zoning_matters()
    for listed in sorted((m for m in matters if is_type_1(m)), key=lambda m: m.record_number, reverse=True):
        if listed.record_number in skipped:
            continue
        detail = await clerk.get_matter(listed.matter_id)
        if detail is None:
            continue
        rows = sample_candidates([detail], limit=1)
        selected.extend(rows)
        if len({row.record_number for row in selected}) == limit:
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
            out.append(SampleCandidate(**{**asdict(row), "download_bytes": size}))
    return out


def private_path(destination: Path, record_number: str, role: str) -> Path:
    return destination / record_number / f"{role}.pdf"


async def download_sample(rows: Iterable[SampleCandidate], destination: Path) -> list[dict]:
    """Download approved public PDFs outside Git with bounded, validated writes.

    Development-only: no serving import calls it.  A packet with any EDS-looking
    or unreadable page is deleted before it is renamed into place, and is
    reported as ``rejected`` (without text) instead of raising, so one bad
    packet does not abort a batch.
    """
    saved: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for row in rows:
            path = private_path(destination, row.record_number, row.role)
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".pdf.part")
            digest = hashlib.sha256()
            total = 0
            entry = {"record_number": row.record_number, "role": row.role, "file_name": row.file_name}
            try:
                async with client.stream("GET", row.url) as response:
                    response.raise_for_status()
                    declared = response.headers.get("Content-Length")
                    if declared and declared.isdigit() and int(declared) > MAX_SAMPLE_FILE_BYTES:
                        raise ValueError("declared size exceeds cap")
                    content_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
                    # Clerk's Azure blob host returns application/octet-stream for
                    # some perfectly valid PDFs. The magic-byte check below remains
                    # mandatory, so accepting this generic type does not trust it.
                    if content_type not in {"application/pdf", "application/octet-stream"}:
                        raise ValueError("response is not a PDF")
                    with partial.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > MAX_SAMPLE_FILE_BYTES:
                                raise ValueError("received size exceeds cap")
                            digest.update(chunk)
                            output.write(chunk)
                if partial.read_bytes()[:5] != b"%PDF-":
                    raise ValueError("PDF signature missing")
                screened = screen_scanned_pages_for_eds(partial, screen_pages_for_eds(partial))
                bad = [page.page for page in screened if page.status in {"eds", "unreadable"}]
                if not screened or bad:
                    partial.unlink(missing_ok=True)
                    saved.append({**entry, "status": "rejected", "pages": bad})
                    continue
                partial.replace(path)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                partial.unlink(missing_ok=True)
                saved.append({**entry, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
                continue
            finally:
                partial.unlink(missing_ok=True)
            saved.append({**entry, "status": "saved", "bytes": total, "sha256": digest.hexdigest(),
                          "pages": len(screened)})
    return saved


@dataclass(frozen=True)
class PageScreen:
    page: int
    status: str  # ordinance | narrative | other | eds | unreadable


def classify_page_text(text: str) -> str:
    """Positive page typing; a missing or uncertain OCR result is never eligible."""
    if _EDS_PAGE.search(text):
        return "eds"
    if len(text.strip()) < 20:
        return "unreadable"
    if _ORDINANCE_PAGE.search(text):
        return "ordinance"
    if _NARRATIVE_PAGE.search(text):
        return "narrative"
    return "other"


def _native_texts(path: Path) -> list[str | None]:
    from pypdf import PdfReader  # dev-only dependency

    texts: list[str | None] = []
    for page in PdfReader(path).pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # malformed individual page; fail closed
            text = None
        texts.append(text if text and text.strip() else None)
    return texts


def _ocr_page(path: Path, page: int) -> str | None:
    try:
        with tempfile.TemporaryDirectory(prefix="urbanlayer-filing-") as directory:
            prefix = Path(directory) / "page"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "200", "-png", "-singlefile", str(path), str(prefix)],
                check=True, capture_output=True,
            )
            return subprocess.run(
                ["tesseract", "stdin", "stdout"], input=prefix.with_suffix(".png").read_bytes(),
                check=True, capture_output=True,
            ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def page_texts(path: Path, cache_dir: Path | None = None) -> list[str | None]:
    """Native text where present, else OCR; ``None`` = unreadable.

    ``cache_dir`` (offline panel runs only) keeps OCR text beside the private
    PDF, keyed by the PDF's SHA-256, so a re-run does not re-OCR.  It must sit
    under the ignored ``research/`` tree; a packet is only ever cached after the
    downloader has retained it, i.e. after its EDS screen passed.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16] if cache_dir else ""
    out: list[str | None] = []
    for number, text in enumerate(_native_texts(path), start=1):
        if text is None and cache_dir:
            cached = cache_dir / f"{path.stem}-{digest}-{number}.txt"
            if cached.exists():
                text = cached.read_text()
            else:
                text = _ocr_page(path, number)
                if text is not None:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cached.write_text(text)
        elif text is None:
            text = _ocr_page(path, number)
        out.append(text)
    return out


def screen_pages_for_eds(path: Path) -> list[PageScreen]:
    """Classify each page from its native text without persisting it.

    An image-only or unreadable page is ``unreadable`` here; the OCR pass below
    must classify it before the packet can be retained.
    """
    return [PageScreen(number, "unreadable" if text is None else classify_page_text(text))
            for number, text in enumerate(_native_texts(path), start=1)]


def screen_scanned_pages_for_eds(path: Path, pages: Iterable[PageScreen]) -> list[PageScreen]:
    """OCR only unreadable pages in memory and retain classifications, never text."""
    out: list[PageScreen] = []
    for result in pages:
        if result.status != "unreadable":
            out.append(result)
            continue
        text = _ocr_page(path, result.page)
        out.append(result if text is None else PageScreen(result.page, classify_page_text(text)))
    return out


def _one(values: list[tuple[str, int]]) -> tuple[str, int] | None:
    """A value stated once, or the same value on one page; anything else is ambiguous."""
    distinct = {value for value, _ in values}
    pages = {page for _, page in values}
    if len(distinct) != 1 or len(pages) != 1:
        return None
    return values[0]


def _number(whole: str | None, fraction: str | None) -> str | None:
    """``"2,978" + "88"`` → ``"2978.88"``; ``".78"`` → ``"0.78"``.  Stated decimals are kept."""
    if not whole and not fraction:
        return None
    value = (whole or "0").replace(",", "")
    return f"{value}.{fraction}" if fraction else value


_DISTRICT_PREFIX = re.compile(r"^(PMD|POS|PD|RS|RT|RM|DX|DC|DR|DS|B|C|M|T)(.*)$")


def _ocr_district(raw: str) -> str:
    """Map OCR letters back in the digit slots only: ``Cl-1`` → ``C1-1``, ``RM-S`` → ``RM-5``."""
    m = _DISTRICT_PREFIX.match(raw.strip())
    if not m or m.group(1) in {"PD", "PMD"}:
        return raw
    return m.group(1) + m.group(2).translate(str.maketrans("lISO", "1150"))


def parse_ordinance_pages(pages: Iterable[tuple[int, str]]) -> list[ParsedField]:
    """From/to district from the reclassification clause(s) of the ordinance.

    ``from_district`` needs exactly one "changing all the <district> ... symbols"
    clause naming exactly one district.  ``to_district`` needs every "to those of
    <district>" on the ordinance to name the same district.  A planned
    development target ("to those of Residential Planned Development No. 1") is
    not a district token and is withheld.
    """
    def district(raw: str) -> str | None:
        return normalize_district(_ocr_district(raw))

    sources: list[tuple[list[str], int]] = []
    targets: list[tuple[str, int]] = []
    for number, text in pages:
        flat = re.sub(r"\s+", " ", text)
        sources += [(_DISTRICT_IN_SPAN.findall(m.group(1)), number) for m in _SOURCE_SPAN.finditer(flat)]
        targets += [(m.group(1), number) for m in _TARGET.finditer(flat)]
    out: list[ParsedField] = []
    if len(sources) == 1 and len(sources[0][0]) == 1:
        source = district(sources[0][0][0])
        if source:
            out.append(ParsedField("from_district", source, None, sources[0][1], "ordinance"))
    normalized = [(district(raw), page) for raw, page in targets]
    if normalized and all(d for d, _ in normalized):
        chosen = _one([(d or "", page) for d, page in normalized])
        if chosen:
            out.append(ParsedField("to_district", chosen[0], None, chosen[1], "ordinance"))
    return out


def parse_narrative_pages(pages: Iterable[tuple[int, str]]) -> list[ParsedField]:
    """Only explicitly labelled Type 1 table values; duplicates and conflicts are withheld.

    No arithmetic, column guessing, or unit conversion.  FAR rows labelled as
    a base/maximum/allowed figure are the district's, not the project's, and
    are skipped.  Dwelling units are withheld when the table separately counts
    efficiency units, because "9 dwelling units" would then understate the
    project.  A height in feet and (non-zero) inches is withheld rather than
    converted.  "Zero"/"None" parking is read as 0.
    """
    found: dict[str, list[tuple[str, int]]] = {key: [] for key in ("lot_area", "far", "dwelling_units", "height", "parking")}
    efficiency = False
    for number, text in pages:
        found["lot_area"] += [(v, number) for m in _LOT_AREA.finditer(text) if (v := _number(m.group(1), m.group(2)))]
        for m in _FAR_LABEL.finditer(text):
            if (m.group(1) or "").strip().lower() not in _FAR_NOT_PROJECT and (v := _number(m.group(2), m.group(3))):
                found["far"].append((v, number))
        found["far"] += [(v, number) for m in _FAR_PAREN.finditer(text) if (v := _number(m.group(1), m.group(2)))]
        found["dwelling_units"] += [(m.group(1), number) for m in _UNITS.finditer(text)]
        for m in _HEIGHT.finditer(text):
            inches = _INCHES.match(text, m.end())
            if inches and not (int(inches.group(1)) == 0 and re.match(r"\s*(?:inch|in\b|\"|”|'')", inches.group(2))):
                found["height"].append(("withheld", number))  # feet + inches: present but not a plain foot value
            else:
                found["height"].append((m.group(1), number))
        for m in _PARKING.finditer(text):
            if (m.group(1) or "").strip().lower() in _PARKING_NOT_CARS:
                continue
            value = m.group(2).lower()
            found["parking"].append(("0" if value in {"zero", "none"} else value, number))
        efficiency = efficiency or bool(_EFFICIENCY.search(text))
    if efficiency:
        found["dwelling_units"] = []
    # v4: a whole-number FAR of 10 or more is almost always a dropped decimal point
    # ("2.17" OCR'd as "217" in held-out O2024-0012331); withhold rather than guess.
    found["far"] = [(v, p) if "." in v or int(v) < 10 else ("withheld", p) for v, p in found["far"]]
    units = {"lot_area": "sq ft", "height": "ft", "parking": "spaces"}
    out: list[ParsedField] = []
    for field_id, values in found.items():
        chosen = _one(values)
        if chosen and chosen[0] != "withheld":
            out.append(ParsedField(field_id, chosen[0], units.get(field_id), chosen[1], "narrative"))
    return out


def parse_labeled_type1_text(text: str) -> list[ParsedField]:
    """Single-page convenience wrapper used by tests and ad hoc review."""
    return parse_narrative_pages([(1, text)])


def title_streets(title: str) -> set[str]:
    """Street-name spellings from a clean Clerk title ("... at 4901 W Ferdinand St") for the narrative check."""
    parsed = address_titles.parse_title(title)
    return {re.sub(r"[^A-Z0-9]", "", spelling) for seg in parsed.segments
            for spelling in address_titles.name_candidates(seg.name)} - {""}


def _names_street(text: str, streets: set[str]) -> bool:
    """Space-insensitive ("Le Moyne" = "LeMoyne"); names under 3 characters never count."""
    squashed = re.sub(r"[^A-Z0-9]", "", text.upper())
    return any(len(street) >= 3 and street in squashed for street in streets)


def read_packet(path: Path, role: str, *, cache_dir: Path | None = None,
                title: str | None = None) -> tuple[list[PageScreen], list[ParsedField]]:
    """Screen and parse one retained private PDF.  Returns classifications and fields, never text.

    Fails closed: any EDS or unreadable page means no fields from this packet.
    v4: a narrative is read only when its parsed pages name a street from the
    matter's Clerk title (held-out O2024-0007192 carried another property's
    narrative); a title with no parseable street means no narrative fields.
    """
    texts = page_texts(path, cache_dir)
    screens = [PageScreen(n, "unreadable" if t is None else classify_page_text(t)) for n, t in enumerate(texts, 1)]
    if not screens or any(s.status in {"eds", "unreadable"} for s in screens):
        return screens, []
    eligible = [(s.page, texts[s.page - 1] or "") for s in screens if s.status == role]
    if role == "narrative" and not _names_street(" ".join(t for _, t in eligible), title_streets(title or "")):
        return screens, []
    parse = parse_ordinance_pages if role == "ordinance" else parse_narrative_pages
    return screens, parse(eligible)


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="WS2 PR4 offline Type 1 filing reader (development only)")
    parser.add_argument("--limit", type=int, default=30, help="matters to select")
    parser.add_argument("--skip", nargs="*", default=(), help="record numbers already sampled")
    parser.add_argument("--head-sizes", action="store_true", help="also make HEAD-only size requests")
    parser.add_argument("--download-dir", type=Path, help="development-only private PDF destination")
    parser.add_argument("--screen-dir", type=Path, help="screen existing private PDFs (prints page types only)")
    args = parser.parse_args(argv)
    if args.screen_dir:
        screened = {
            str(pdf.relative_to(args.screen_dir)): [asdict(page) for page in screen_scanned_pages_for_eds(pdf, screen_pages_for_eds(pdf))]
            for pdf in sorted(args.screen_dir.glob("*/*.pdf"))
        }
        print(json.dumps(screened, indent=2))
        return 0
    try:
        rows = await build_download_manifest(limit=args.limit, skip=args.skip)
    except (clerk.ClerkUnavailable, clerk.ClerkQueryError, ValueError) as exc:
        print(f"filing reader manifest: failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.head_sizes:
        rows = await add_head_sizes(rows)
    if args.download_dir:
        saved = await download_sample(rows, args.download_dir)
        print(json.dumps({"downloaded": saved}, indent=2))
        return 0
    print(json.dumps({"files": [asdict(row) for row in rows], "total_bytes": sum(
        row.download_bytes or 0 for row in rows), "unknown_sizes": sum(row.download_bytes is None for row in rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
