"""Parse the American Legal Publishing HTML export of the Chicago Municipal Code.

Input: chicago-il-codes.html (a single ~100MB file at the project root).
Output: one JSON file per section under ingestion/data/sections/{section_id}.json.

The parser walks the file in document order using BeautifulSoup, maintaining a
state machine for the current Title / Chapter / Article / Subarticle / Part.
A Section header (`<div class="Section toc-destination rbox">`) opens a new
section; all subsequent body `rbox` divs (Normal-Level / Indent1 / Indent2 etc.)
attach to it until the next hierarchy or Section boundary is encountered.

Run with:
    python -m ingestion.parse_chicago_code
    python -m ingestion.parse_chicago_code --title 17     # only Title 17
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup, Tag


log = logging.getLogger(__name__)

SOURCE_FILE = Path(__file__).resolve().parent.parent / "chicago-il-codes.html"
OUT_DIR = Path(__file__).resolve().parent / "data" / "sections"

SECTION_RE = re.compile(r"^(\d+-\d+-\d+(?:\.\d+)?)\s+(.+)", re.DOTALL)
TITLE_RE = re.compile(r"^TITLE\s+(\d+)\s*(.*)$", re.IGNORECASE | re.DOTALL)
CHAPTER_RE = re.compile(r"^CHAPTER\s+(\d+-\d+)\s*(.*)$", re.IGNORECASE | re.DOTALL)
ARTICLE_RE = re.compile(r"^ARTICLE\s+([IVXLCDM]+|\d+)\s*\.?\s*(.*)$", re.IGNORECASE | re.DOTALL)
SUBARTICLE_RE = re.compile(r"^SUBARTICLE\s+([IVXLCDM]+|\d+)\s*\.?\s*(.*)$", re.IGNORECASE | re.DOTALL)
PART_RE = re.compile(r"^PART\s+([IVXLCDM]+|\d+)\s*\.?\s*(.*)$", re.IGNORECASE | re.DOTALL)
JD_HASH_RE = re.compile(r"#JD_([A-Za-z0-9._-]+)")
LEG_HISTORY_RE = re.compile(r"^\s*\(\s*(Added|Amend|Repealed|Prior)", re.IGNORECASE)
DEFINITION_RE = re.compile(r"(?:^|\.\s+)\"([^\"]{2,80})\"\s+(?:means|shall mean|refers to)", re.IGNORECASE)
EFFECTIVE_DATE_RE = re.compile(r"Coun\.\s*J\.\s*(\d{1,2}-\d{1,2}-\d{2,4})")


@dataclass
class StructuredTable:
    """A table with multi-row headers resolved into per-column composite labels.

    `headers` is a list of composite header labels — one per logical column,
    e.g. ["USE GROUP - Use Category", "RS-1", "RS-2", ..., "Use Standard"].
    `data_rows` is the list of data rows, each aligned to the column count.
    `caption` is any pre-table title text the parser was able to associate.
    """
    headers: list[str]
    data_rows: list[list[str]]
    caption: str = ""


@dataclass
class Section:
    section: str                          # canonical anchor, e.g. "17-2-0100"
    section_title: str                    # human title
    title_number: int | None = None
    title_name: str = ""
    chapter: str | None = None
    chapter_name: str = ""
    article: str | None = None
    article_name: str = ""
    subarticle: str | None = None
    subarticle_name: str = ""
    part: str | None = None
    part_name: str = ""
    body_paragraphs: list[str] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    cross_references: list[str] = field(default_factory=list)
    legislative_history: str | None = None
    effective_dates: list[str] = field(default_factory=list)
    definitions: list[str] = field(default_factory=list)
    has_table: bool = False
    prev_section: str | None = None
    next_section: str | None = None


def _txt(tag: Tag) -> str:
    """Normalized text from a tag with non-breaking spaces collapsed."""
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def _classes(tag: Tag) -> set[str]:
    cls = tag.get("class") or []
    return set(cls if isinstance(cls, list) else cls.split())


def _extract_anchor(tag: Tag) -> str | None:
    a = tag.find("a", attrs={"name": True})
    if a:
        name = a.get("name", "")
        if name.startswith("JD_"):
            return name[3:]
    return None


def _extract_cross_refs(tag: Tag) -> list[str]:
    """Pull every JD_ anchor referenced from Link tags. Returns canonical anchor
    names like '17-2-0100', 'Ch.17-2', or 'Title17' — caller can decide how to
    resolve each shape."""
    refs: list[str] = []
    # lxml lowercases custom tag names: <Link> -> <link>. The Jump class disambiguates
    # from native <link> stylesheet refs.
    for link in tag.find_all("link"):
        if "Jump" not in (link.get("class") or []):
            continue
        to = link.get("to", "")
        m = JD_HASH_RE.search(to)
        if m:
            refs.append(m.group(1))
    return refs


def _expand_table_grid(table: Tag) -> list[list[str]]:
    """Expand a table into a rectangular 2D grid, resolving colspan/rowspan.

    HTML tables with rowspan/colspan are NOT rectangular at the source level —
    a `rowspan=3` cell occupies one slot in three consecutive rows but is only
    listed in the markup once. To compose accurate composite headers and to
    align data cells to columns, we materialize the grid by walking rows and
    "carrying down" rowspan cells from prior rows.
    """
    grid: list[list[str]] = []
    rowspan_carry: dict[int, tuple[str, int]] = {}  # col_idx -> (text, rows_remaining)
    for tr in table.find_all("tr"):
        row: list[str] = []
        cell_iter = iter(tr.find_all(["td", "th"]))
        col = 0
        while True:
            # If a prior row's rowspan still applies at this column, place it.
            if col in rowspan_carry:
                text, remaining = rowspan_carry[col]
                row.append(text)
                if remaining - 1 > 0:
                    rowspan_carry[col] = (text, remaining - 1)
                else:
                    del rowspan_carry[col]
                col += 1
                continue
            try:
                cell = next(cell_iter)
            except StopIteration:
                # If carries remain to the right, keep filling so all rows line up
                if any(k > col for k in rowspan_carry):
                    continue
                break
            text = _txt(cell)
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for offset in range(colspan):
                if rowspan > 1:
                    rowspan_carry[col + offset] = (text, rowspan - 1)
                row.append(text)
            col += colspan
        if row:
            grid.append(row)
    # Normalize ragged rows to the max width
    width = max((len(r) for r in grid), default=0)
    for r in grid:
        if len(r) < width:
            r.extend([""] * (width - len(r)))
    return grid


def _split_header_rows(grid: list[list[str]]) -> tuple[int, list[str]]:
    """Decide how many leading rows of `grid` form the composite header, then
    compose one label per column by joining each column's header-row values
    (deduping consecutive repeats).
    """
    if not grid:
        return 0, []

    # Heuristic: the number of header rows equals the maximum rowspan seen in
    # row 1. We approximated rowspan at parse time by carry-down; we can
    # recover it by counting how many consecutive rows hold the same value in a
    # column starting from row 0. Use the maximum such consecutive run across
    # any column in row 0 as the header-row count, but cap at 4 to be safe.
    width = len(grid[0])
    n_header = 1
    for c in range(width):
        if not grid[0][c]:
            continue
        same = 1
        while same < min(len(grid), 4) and grid[same][c] == grid[0][c]:
            same += 1
        n_header = max(n_header, same)

    headers: list[str] = []
    for c in range(width):
        parts: list[str] = []
        last = None
        for r in range(n_header):
            v = grid[r][c].strip() if c < len(grid[r]) else ""
            if v and v != last:
                parts.append(v)
                last = v
        headers.append(" - ".join(parts) if parts else f"col{c+1}")
    return n_header, headers


def _extract_tables(tag: Tag) -> list[dict]:
    """Extract tables as structured dicts with composite headers and data rows."""
    out: list[dict] = []
    for table in tag.find_all("table"):
        grid = _expand_table_grid(table)
        if not grid:
            continue
        n_header, headers = _split_header_rows(grid)
        data_rows = grid[n_header:]
        # Skip empty data tables (sometimes used for layout)
        if not any(any(c.strip() for c in row) for row in data_rows):
            continue
        out.append({
            "headers": headers,
            "data_rows": data_rows,
            "caption": "",
        })
    return out


def _is_hierarchy_div(tag: Tag) -> str | None:
    """Return 'title' / 'chapter' / 'article' / 'subarticle' / 'part' / 'section' or None.

    The `toc-destination` class is inconsistently applied across the document
    (the PREFACE chapter has it; Chapter 17-2 does not). We rely on the
    hierarchy class name alone and explicitly exclude the TOC-listing
    counterparts (Chapter-Analysis, ChapterAnalysis-center).
    """
    cls = _classes(tag)
    if "Chapter-Analysis" in cls or "ChapterAnalysis-center" in cls:
        return None
    if "Section" in cls:
        return "section"
    if "Subsection" in cls:
        return "subsection"
    if "Title" in cls or "Title-Part" in cls:
        return "title"
    if "Chapter" in cls:
        return "chapter"
    if "Article" in cls:
        return "article"
    if "Subarticle" in cls:
        return "subarticle"
    if "Part" in cls:
        return "part"
    return None


def _is_skip(tag: Tag) -> bool:
    cls = _classes(tag)
    return bool(cls & {"Chapter-Analysis", "ChapterAnalysis-center", "clearfix"})


@dataclass
class _State:
    title_number: int | None = None
    title_name: str = ""
    chapter: str | None = None
    chapter_name: str = ""
    article: str | None = None
    article_name: str = ""
    subarticle: str | None = None
    subarticle_name: str = ""
    part: str | None = None
    part_name: str = ""

    def reset_below(self, level: str) -> None:
        order = ["title", "chapter", "article", "subarticle", "part"]
        idx = order.index(level)
        if idx < 1:
            self.chapter = None
            self.chapter_name = ""
        if idx < 2:
            self.article = None
            self.article_name = ""
        if idx < 3:
            self.subarticle = None
            self.subarticle_name = ""
        if idx < 4:
            self.part = None
            self.part_name = ""


# The HTML export contains some malformed markup partway through Title 18 that
# causes lxml/html.parser to nest the trailing ~8MB (the republication of
# Titles 16/17 as a standalone Zoning Ordinance + Land Use Ordinance volume)
# inside an earlier element rather than at body level. We detect the
# republication boundary by its banner text and parse the two halves
# independently, then stream sections from both — the dedup logic in emit()
# already protects against double-counting overlapping anchors.
_REPUBLICATION_MARKER = "CHICAGO ZONING ORDINANCE<br></br>AND LAND USE ORDINANCE"


def _iter_body_top_divs(html_text: str) -> Iterator[Tag]:
    """Yield top-level body divs from one or more parsed segments. If the file
    contains the republication marker, parse pre/post separately so trailing
    content isn't swallowed by lxml's error recovery."""
    cut = html_text.find(_REPUBLICATION_MARKER)
    segments: list[str]
    if cut == -1:
        segments = [html_text]
    else:
        # Walk backwards to the start of the enclosing top-level <div> for the
        # republication banner — that way the marker stays on the second half.
        prefix = html_text[:cut]
        # Heuristic: the republication banner is wrapped in
        # `<div><div id="rid-...-48006" class="rbox Title">` — find that opener.
        marker_start = prefix.rfind("<div><div id=", max(0, cut - 200))
        if marker_start == -1:
            marker_start = cut
        first = html_text[:marker_start]
        second = "<html><body>" + html_text[marker_start:]
        segments = [first, second]
        log.info("Split into %d segments at republication boundary (offset %d)", len(segments), marker_start)

    for i, seg in enumerate(segments):
        soup = BeautifulSoup(seg, "lxml")
        body = soup.body or soup
        log.info("Segment %d: %d top-level body divs", i + 1, len(body.find_all("div", recursive=False)))
        for div in body.find_all("div", recursive=False):
            yield div


def parse(
    html_path: Path,
    only_title: int | None = None,
    *,
    stats: dict | None = None,
) -> Iterator[Section]:
    html = html_path.read_text(encoding="utf-8")
    log.info("Parsing %s (%.1f MB)", html_path.name, len(html) / 1e6)

    state = _State()
    current: Section | None = None
    skipping_title = False
    prev_emitted_id: str | None = None
    pending_prev_link: Section | None = None
    # The file contains two copies of Titles 16/17 — once inside the Municipal
    # Code and once as a republication near the tail of the file. Dedupe so the
    # first (Municipal Code) copy wins and the second is silently dropped.
    seen_section_ids: set[str] = set()

    def emit(sec: Section) -> Iterator[Section]:
        nonlocal prev_emitted_id, pending_prev_link
        if sec.section in seen_section_ids:
            if stats is not None:
                stats["dedup_skipped"] = stats.get("dedup_skipped", 0) + 1
            return
        seen_section_ids.add(sec.section)
        if pending_prev_link is not None:
            pending_prev_link.next_section = sec.section
            yield pending_prev_link
        sec.prev_section = prev_emitted_id
        prev_emitted_id = sec.section
        pending_prev_link = sec

    for outer in _iter_body_top_divs(html):
        # Each outer div may itself contain many inner divs that represent a unit
        # (title heading + chapter TOC, or a section header + its body). Walk them.
        inner_divs = outer.find_all("div", recursive=False) or [outer]
        for div in inner_divs:
            if _is_skip(div):
                continue

            kind = _is_hierarchy_div(div)

            if kind == "title":
                if current is not None:
                    yield from emit(current)
                    current = None
                txt = _txt(div)
                m = TITLE_RE.match(txt)
                if m:
                    state.title_number = int(m.group(1))
                    state.title_name = m.group(2).strip(" .:")
                    state.reset_below("title")
                    skipping_title = only_title is not None and state.title_number != only_title
                continue

            if skipping_title:
                continue

            if kind == "chapter":
                if current is not None:
                    yield from emit(current)
                    current = None
                txt = _txt(div)
                m = CHAPTER_RE.match(txt)
                if m:
                    state.chapter = m.group(1)
                    state.chapter_name = m.group(2).strip(" .:")
                    state.reset_below("chapter")
                continue

            if kind == "article":
                if current is not None:
                    yield from emit(current)
                    current = None
                txt = _txt(div)
                m = ARTICLE_RE.match(txt)
                if m:
                    state.article = m.group(1)
                    state.article_name = m.group(2).strip(" .:")
                    state.reset_below("article")
                continue

            if kind == "subarticle":
                if current is not None:
                    yield from emit(current)
                    current = None
                txt = _txt(div)
                m = SUBARTICLE_RE.match(txt)
                if m:
                    state.subarticle = m.group(1)
                    state.subarticle_name = m.group(2).strip(" .:")
                    state.reset_below("subarticle")
                continue

            if kind == "part":
                if current is not None:
                    yield from emit(current)
                    current = None
                txt = _txt(div)
                m = PART_RE.match(txt)
                if m:
                    state.part = m.group(1)
                    state.part_name = m.group(2).strip(" .:")
                    state.reset_below("part")
                continue

            if kind == "section":
                if current is not None:
                    yield from emit(current)
                anchor = _extract_anchor(div)
                txt = _txt(div)
                m = SECTION_RE.match(txt)
                section_id = anchor or (m.group(1) if m else txt[:32])
                section_title = (m.group(2) if m else "").rstrip(". ").strip()
                current = Section(
                    section=section_id,
                    section_title=section_title,
                    title_number=state.title_number,
                    title_name=state.title_name,
                    chapter=state.chapter,
                    chapter_name=state.chapter_name,
                    article=state.article,
                    article_name=state.article_name,
                    subarticle=state.subarticle,
                    subarticle_name=state.subarticle_name,
                    part=state.part,
                    part_name=state.part_name,
                )
                continue

            # Body div — only attach to an open section
            if current is None:
                continue

            # Tables get pulled separately. Skip adding the run-on text of a
            # div that contains a table to body_paragraphs — the structured
            # `tables` list captures the same content with proper labels.
            tables = _extract_tables(div)
            if tables:
                current.tables.extend(tables)
                current.has_table = True
                continue

            body_text = _txt(div)
            if not body_text:
                continue

            refs = _extract_cross_refs(div)
            for r in refs:
                if r not in current.cross_references and r != current.section:
                    current.cross_references.append(r)

            if LEG_HISTORY_RE.match(body_text):
                current.legislative_history = body_text
                for d in EFFECTIVE_DATE_RE.findall(body_text):
                    if d not in current.effective_dates:
                        current.effective_dates.append(d)
                continue

            for term in DEFINITION_RE.findall(body_text):
                if term not in current.definitions:
                    current.definitions.append(term)

            current.body_paragraphs.append(body_text)

    if current is not None:
        yield from emit(current)
    if pending_prev_link is not None:
        yield pending_prev_link


def _print_stats(stats: dict) -> None:
    by_title: dict[int | None, dict] = stats["by_title"]
    titles = sorted(by_title.keys(), key=lambda t: (t is None, t or 0))
    print(f"{'Title':>6} {'Sections':>10} {'Tables':>8} {'XRefs':>8} {'Defs':>6} {'LegHist':>8} {'EmptyBody':>10} {'TinyBody':>9}")
    print("-" * 78)
    for t in titles:
        b = by_title[t]
        print(
            f"{str(t) if t is not None else '—':>6} "
            f"{b['sections']:>10} "
            f"{b['tables']:>8} "
            f"{b['sections_with_xrefs']:>8} "
            f"{b['sections_with_defs']:>6} "
            f"{b['sections_with_leg']:>8} "
            f"{b['empty_body']:>10} "
            f"{b['tiny_body']:>9}"
        )
    print("-" * 78)
    print(
        f"{'TOTAL':>6} "
        f"{stats['total_sections']:>10} "
        f"{stats['total_tables']:>8} "
        f"{stats['total_xref_sections']:>8} "
        f"{stats['total_def_sections']:>6} "
        f"{stats['total_leg_sections']:>8} "
        f"{stats['total_empty_body']:>10} "
        f"{stats['total_tiny_body']:>9}"
    )
    print()
    print(f"Non-section entries skipped: {stats['skipped_non_section']}")
    print(f"Duplicate section IDs skipped (file republishes Titles 16/17): {stats['dedup_skipped']}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", type=int, default=None, help="Limit to a single title number (e.g. 17)")
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_FILE,
        help="Path to the chicago-il-codes.html file",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Compute and print per-title coverage stats; skip JSON output",
    )
    args = parser.parse_args()

    if not args.source.exists():
        sys.exit(f"Source file not found: {args.source}")

    if not args.stats:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_sections": 0,
        "total_tables": 0,
        "total_xref_sections": 0,
        "total_def_sections": 0,
        "total_leg_sections": 0,
        "total_empty_body": 0,
        "total_tiny_body": 0,
        "skipped_non_section": 0,
        "dedup_skipped": 0,
        "by_title": {},
    }

    count = 0
    for section in parse(args.source, only_title=args.title, stats=stats):
        if not section.section or not re.fullmatch(r"\d+-\d+-\d+(?:\.\d+)?", section.section):
            stats["skipped_non_section"] += 1
            continue

        body_chars = sum(len(p) for p in section.body_paragraphs)
        t = section.title_number
        b = stats["by_title"].setdefault(
            t,
            {
                "sections": 0,
                "tables": 0,
                "sections_with_xrefs": 0,
                "sections_with_defs": 0,
                "sections_with_leg": 0,
                "empty_body": 0,
                "tiny_body": 0,
            },
        )
        b["sections"] += 1
        b["tables"] += len(section.tables)
        if section.cross_references:
            b["sections_with_xrefs"] += 1
        if section.definitions:
            b["sections_with_defs"] += 1
        if section.legislative_history:
            b["sections_with_leg"] += 1
        if body_chars == 0 and not section.tables:
            b["empty_body"] += 1
        elif body_chars < 100 and not section.tables:
            b["tiny_body"] += 1

        stats["total_sections"] += 1
        stats["total_tables"] += len(section.tables)
        stats["total_xref_sections"] += bool(section.cross_references)
        stats["total_def_sections"] += bool(section.definitions)
        stats["total_leg_sections"] += bool(section.legislative_history)
        stats["total_empty_body"] += (body_chars == 0 and not section.tables)
        stats["total_tiny_body"] += (0 < body_chars < 100 and not section.tables)

        if not args.stats:
            out_path = OUT_DIR / f"{section.section}.json"
            out_path.write_text(json.dumps(asdict(section), indent=2))
        count += 1
        if not args.stats and count % 1000 == 0:
            log.info("Parsed %d sections", count)

    if args.stats:
        _print_stats(stats)
    else:
        log.info(
            "Done. %d sections written to %s. %d non-section entries skipped.",
            count, OUT_DIR, stats["skipped_non_section"],
        )


if __name__ == "__main__":
    main()
