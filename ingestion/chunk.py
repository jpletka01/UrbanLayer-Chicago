"""Section-aware chunker for Chicago Municipal Code sections.

Reads section JSON files from ingestion/data/sections/ (produced by
ingestion.parse_chicago_code) and emits chunks to ingestion/data/chunks.jsonl.

Key invariants:
  - Each chunk's text starts with a self-contained hierarchical header so the
    LLM can interpret the snippet without needing surrounding context.
  - Sections are not split unless they exceed MAX_CHARS. When split, splits
    happen at paragraph boundaries and never inside a table.
  - Tables are flattened to "row N: col1=val1; col2=val2" form so the embedding
    model treats them as legible prose rather than mangled pipe-tables.
  - Cross-references, prev/next adjacency, legislative history, effective
    dates, and a `has_table` flag travel in the payload so retrieval-time
    expansion ("see also") works without re-parsing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator


log = logging.getLogger(__name__)

SECTIONS_DIR = Path(__file__).resolve().parent / "data" / "sections"
OUT_FILE = Path(__file__).resolve().parent / "data" / "chunks.jsonl"

# BAAI/bge-small-en-v1.5 has max_seq_length=512 tokens. Use ~1800 chars (~450
# tokens, leaving headroom for the header block) as the soft max per chunk.
MAX_CHARS = 1800
HARD_MAX_CHARS = 2400  # tolerate slightly over to avoid splitting mid-paragraph


@dataclass
class Chunk:
    text: str
    source_document: str
    section: str
    section_title: str
    title_number: int | None
    title_name: str
    chapter: str | None
    chapter_name: str
    article: str | None
    article_name: str
    subarticle: str | None
    subarticle_name: str
    part: str | None
    part_name: str
    subsection: str | None
    chunk_index: int
    chunk_count: int
    cross_references: list[str] = field(default_factory=list)
    prev_section: str | None = None
    next_section: str | None = None
    legislative_history: str | None = None
    effective_dates: list[str] = field(default_factory=list)
    definitions: list[str] = field(default_factory=list)
    has_table: bool = False


def _header_block(sec: dict, part: str | None = None) -> str:
    """Self-contained location header prepended to every chunk's text."""
    lines = ["CHICAGO MUNICIPAL CODE"]
    if sec.get("title_number") is not None:
        tname = sec.get("title_name") or ""
        lines.append(f"Title {sec['title_number']}{' — ' + tname if tname else ''}")
    if sec.get("chapter"):
        cname = sec.get("chapter_name") or ""
        lines.append(f"Chapter {sec['chapter']}{' — ' + cname if cname else ''}")
    if sec.get("article"):
        aname = sec.get("article_name") or ""
        lines.append(f"Article {sec['article']}{' — ' + aname if aname else ''}")
    if sec.get("subarticle"):
        sname = sec.get("subarticle_name") or ""
        lines.append(f"Subarticle {sec['subarticle']}{' — ' + sname if sname else ''}")
    if sec.get("part"):
        pname = sec.get("part_name") or ""
        lines.append(f"Part {sec['part']}{' — ' + pname if pname else ''}")
    title = (sec.get("section_title") or "").strip()
    lines.append(f"§ {sec['section']}{' — ' + title if title else ''}")
    if part:
        lines.append(part)
    return "\n".join(lines)


# Width threshold (in columns) above which a colspan'd row counts as a
# sub-section header *inside* a large table (e.g. "A. Household Living").
SUBHEADER_COVERAGE = 0.5
# Soft limit per emitted table block (in chars). Above this we split at the
# next sub-header row.
TABLE_BLOCK_CHARS = 1600


def _is_subheader_row(row: list[str], width: int) -> bool:
    """A row is a sub-section header inside a table when its non-empty cells
    all share the same value spanning most of the row — a common pattern in the
    use table for category labels like "RESIDENTIAL" or "A. Household Living"
    that originally had a single colspan-all-columns cell in the source HTML
    (which colspan expansion materializes as many duplicate cells).
    """
    if not row:
        return False
    non_empty = [c.strip() for c in row if c.strip()]
    if not non_empty:
        return False
    if len(set(non_empty)) != 1:
        return False
    text = non_empty[0]
    # Category labels are short ("RESIDENTIAL", "A. Household Living"); legends
    # and footnotes that happen to be colspan-all-columns are long. Cap to keep
    # them out of the subheader bucket.
    if len(text) > 80:
        return False
    return len(non_empty) / max(width, 1) >= SUBHEADER_COVERAGE


def _flatten_row(headers: list[str], row: list[str], idx: int) -> str:
    """Render a row as `Row N: header=value; header=value`. When all non-empty
    cells share one value (typically because the source HTML used a single
    colspan-all-columns cell that we materialized as duplicates), collapse to
    `Row N (all columns): value` for legibility."""
    non_empty = [c.strip() for c in row if c.strip()]
    if non_empty and len(set(non_empty)) == 1 and len(non_empty) >= max(2, len(row) // 2):
        return f"Row {idx} (all columns): {non_empty[0]}"

    cells = []
    last_label_value: tuple[str, str] | None = None
    for j, cell in enumerate(row):
        label = headers[j] if j < len(headers) and headers[j] else f"col{j+1}"
        value = cell.strip()
        if not value:
            continue
        # Skip consecutive duplicate label+value pairs from colspan expansion
        if last_label_value == (label, value):
            continue
        cells.append(f"{label}: {value}")
        last_label_value = (label, value)
    return f"Row {idx}: " + "; ".join(cells) if cells else ""


def _flatten_table_blocks(table: dict) -> list[str]:
    """Flatten a structured table into one or more text blocks. Splits at
    sub-header rows when the table is large; small tables stay as one block.

    Returns a list of strings; each string is a self-contained text block
    that starts with a header line so it's interpretable on its own. Caller
    can pack these into chunks.
    """
    headers = table.get("headers") or []
    rows = table.get("data_rows") or []
    if not rows:
        return []
    width = len(headers) or (len(rows[0]) if rows else 0)
    header_line = "Columns: " + " | ".join(h for h in headers if h)

    blocks: list[str] = []
    current_subheader = ""
    current_rows: list[str] = []
    row_idx = 0

    def flush() -> None:
        nonlocal current_rows
        if not current_rows:
            return
        prelude = [header_line]
        if current_subheader:
            prelude.append(f"Section: {current_subheader}")
        blocks.append("\n".join(prelude) + "\n" + "\n".join(current_rows))
        current_rows = []

    char_count = 0
    for raw_row in rows:
        if _is_subheader_row(raw_row, width):
            flush()
            current_subheader = next((c for c in raw_row if c.strip()), "")
            char_count = 0
            continue
        row_idx += 1
        flat = _flatten_row(headers, raw_row, row_idx)
        if not flat:
            continue
        if current_rows and char_count + len(flat) > TABLE_BLOCK_CHARS:
            flush()
            char_count = 0
        current_rows.append(flat)
        char_count += len(flat) + 1
    flush()
    return blocks


def _body_with_tables(sec: dict) -> str:
    """Return body text with each table represented as one or more [TABLE]
    blocks. Multi-block tables stay adjacent so they can be split into chunks
    at table-block boundaries — never mid-block."""
    out: list[str] = []
    for p in sec.get("body_paragraphs", []):
        p = (p or "").strip()
        if p:
            out.append(p)
    for table in sec.get("tables", []):
        # Support both the legacy list-of-list format and the new structured dict
        if isinstance(table, list):
            # legacy path — render with naive header detection
            if not table:
                continue
            headers = [c.strip() for c in table[0]]
            data = table[1:]
            blocks = _flatten_table_blocks({"headers": headers, "data_rows": data})
        else:
            blocks = _flatten_table_blocks(table)
        for b in blocks:
            out.append("[TABLE]\n" + b)
    return "\n\n".join(out)


def _split_body(body: str, budget: int) -> list[str]:
    """Split body at paragraph boundaries, packing under `budget` chars per piece.
    Never splits inside a [TABLE] block."""
    pieces: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in body.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        # Tables stay intact even if they exceed budget
        if para.startswith("[TABLE]") or len(para) + buf_len + 2 > HARD_MAX_CHARS:
            if buf:
                pieces.append("\n\n".join(buf))
                buf = []
                buf_len = 0
            pieces.append(para)
            continue
        if buf_len + len(para) + 2 > budget and buf:
            pieces.append("\n\n".join(buf))
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        pieces.append("\n\n".join(buf))
    return pieces or [""]


def chunk_section(sec: dict) -> Iterator[Chunk]:
    body = _body_with_tables(sec)
    if not body:
        return

    header = _header_block(sec)
    header_len = len(header)
    body_budget = max(800, MAX_CHARS - header_len - 40)

    pieces = _split_body(body, body_budget) if len(body) > body_budget else [body]
    total = len(pieces)

    leg = sec.get("legislative_history")

    for i, piece in enumerate(pieces, start=1):
        part_label = f"(part {i} of {total})" if total > 1 else None
        text_parts = [_header_block(sec, part_label), piece.strip()]
        if i == total and leg:
            text_parts.append(f"Legislative history: {leg}")
        text = "\n\n".join(p for p in text_parts if p)

        yield Chunk(
            text=text,
            source_document="Chicago Municipal Code",
            section=sec["section"],
            section_title=sec.get("section_title", ""),
            title_number=sec.get("title_number"),
            title_name=sec.get("title_name", ""),
            chapter=sec.get("chapter"),
            chapter_name=sec.get("chapter_name", ""),
            article=sec.get("article"),
            article_name=sec.get("article_name", ""),
            subarticle=sec.get("subarticle"),
            subarticle_name=sec.get("subarticle_name", ""),
            part=sec.get("part"),
            part_name=sec.get("part_name", ""),
            subsection=None,
            chunk_index=i,
            chunk_count=total,
            cross_references=sec.get("cross_references", []),
            prev_section=sec.get("prev_section"),
            next_section=sec.get("next_section"),
            legislative_history=leg,
            effective_dates=sec.get("effective_dates", []),
            definitions=sec.get("definitions", []),
            has_table=bool(sec.get("has_table")),
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not SECTIONS_DIR.exists():
        raise SystemExit(
            f"No parsed sections at {SECTIONS_DIR} — run ingestion.parse_chicago_code first"
        )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    sections_seen = 0
    with OUT_FILE.open("w") as fh:
        for path in sorted(SECTIONS_DIR.glob("*.json")):
            section = json.loads(path.read_text())
            sections_seen += 1
            for chunk in chunk_section(section):
                fh.write(json.dumps(asdict(chunk)) + "\n")
                count += 1
            if sections_seen % 1000 == 0:
                log.info("Processed %d sections, emitted %d chunks", sections_seen, count)
    log.info("Done. %d chunks from %d sections written to %s", count, sections_seen, OUT_FILE)


if __name__ == "__main__":
    main()
