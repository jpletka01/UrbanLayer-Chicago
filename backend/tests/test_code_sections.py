"""V2: cut one subsection (and its table) out of an indexed article, so a Profile
number can show the exact code text it came from. The article text is rebuilt here in
the index's own format (paragraphs, then ``[TABLE]`` blocks) from the ingested JSON."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.code_sections import SECTION_ID_RE, TABLE_HINTS, article_id, set_indexed_sections

SECTIONS = Path(__file__).resolve().parents[2] / "ingestion" / "data" / "sections"
FILES = ["17-2-0300", "17-3-0400", "17-4-0400", "17-5-0400"]


def _article(file: str) -> str:
    path = SECTIONS / f"{file}.json"
    if not path.exists():
        pytest.skip("ordinance corpus not present")
    d = json.loads(path.read_text())
    out = "\n\n".join(d["body_paragraphs"])
    for t in d["tables"]:
        rows = "\n".join(
            "Row {}: {}".format(i + 1, "; ".join(f"{h}: {c}" for h, c in zip(t["headers"], r)))
            for i, r in enumerate(t["data_rows"])
        )
        out += "\n\n[TABLE]\nColumns: " + " | ".join(h or "" for h in t["headers"]) + "\n" + rows
    return out


# --- ids ----------------------------------------------------------------------------

def test_article_ids():
    assert [article_id(x) for x in ("17-2-0304-A", "17-2-0300", "17-3-0408-A", "17-4-0407", "17-10-0102-B", "2-120-740")] == [
        "17-2-0300", "17-2-0300", "17-3-0400", "17-4-0400", "17-10-0100", "2-120-740"]


def test_article_ids_come_from_the_index(indexed_code):
    """Chapter 17-7 starts articles off the hundred: the ADU section 17-7-0574 lives in
    17-7-0570 and 606's 17-7-0591 in 17-7-0590 (both 404'd when rounded to 17-7-0500)."""
    assert {x: article_id(x) for x in (
        "17-7-0574", "17-7-0591", "17-7-0593-A", "17-7-0513", "17-7-0503", "17-7-0459", "17-7-0570",
        "17-2-0304-A", "17-3-0503-D", "17-11-0055", "11-4-1010", "2-120-740",
    )} == {
        "17-7-0574": "17-7-0570", "17-7-0591": "17-7-0590", "17-7-0593-A": "17-7-0590", "17-7-0513": "17-7-0510",
        "17-7-0503": "17-7-0500", "17-7-0459": "17-7-0450", "17-7-0570": "17-7-0570",
        "17-2-0304-A": "17-2-0300", "17-3-0503-D": "17-3-0500", "17-11-0055": "17-11-0050",
        "11-4-1010": "11-4-1010", "2-120-740": "2-120-740",
    }


def test_article_ids_never_cross_into_the_next_hundred(indexed_code):
    # 17-3-0600 (TOD Streets) isn't in the text yet: it is its own id, not part of 17-3-0500
    assert article_id("17-3-0600") == "17-3-0600" and article_id("17-3-0601-A") == "17-3-0600"
    # a chapter the index doesn't hold, and an unregistered index, fall back to the hundred
    assert article_id("17-99-0574") == "17-99-0500"
    set_indexed_sections(())
    assert article_id("17-7-0574") == "17-7-0500"


@pytest.mark.parametrize("bad", ["../etc/passwd", "17-2-0304-a", "17-2", "17-2-0304-AB", "", "17-2-0304; drop", "abc"])
def test_section_id_validation_rejects_anything_that_is_not_a_section(bad):
    assert not SECTION_ID_RE.match(bad)


# --- extraction from the real articles --------------------------------------------------


def test_table_hints_match_the_codes_real_column_headers():
    for sec, (include, exclude) in TABLE_HINTS.items():
        art = _article(next(f for f in FILES if f == article_id(sec)))
        cols = [b.split("\n", 1)[0] for b in art.split("\n[TABLE]\n")[1:]]
        hits = [c for c in cols if all(s in c for s in include) and not any(s in c for s in exclude)]
        assert hits, (sec, include)


# --- the endpoint -------------------------------------------------------------------------------


def test_scrolling_the_index_registers_its_articles(monkeypatch):
    """vector_search's one-time section scroll is what feeds article_id in the app."""
    from unittest.mock import MagicMock

    from backend.retrieval import vector_search as vs

    page = MagicMock()
    page.json.return_value = {"result": {"points": [{"payload": {"section": s}} for s in ("17-7-0500", "17-7-0570")],
                                         "next_page_offset": None}}
    qdrant = MagicMock(post=AsyncMock(return_value=page))
    monkeypatch.setattr(vs, "_known_sections_cache", None)
    monkeypatch.setattr(vs, "_get_qdrant_client", lambda: qdrant)
    monkeypatch.setattr(vs, "get_settings", lambda: MagicMock(qdrant_url="http://q", qdrant_code_collection="c"))

    assert article_id("17-7-0574") == "17-7-0500"
    asyncio.run(vs._get_known_sections())
    assert article_id("17-7-0574") == "17-7-0570"
