"""V2: cut one subsection (and its table) out of an indexed article, so a Profile
number can show the exact code text it came from. The article text is rebuilt here in
the index's own format (paragraphs, then ``[TABLE]`` blocks) from the ingested JSON."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.code_sections import SECTION_ID_RE, TABLE_HINTS, article_id, extract_subsection
from backend.models import CodeChunk
from backend.provenance import BULK_SECTIONS

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


@pytest.mark.parametrize("bad", ["../etc/passwd", "17-2-0304-a", "17-2", "17-2-0304-AB", "", "17-2-0304; drop", "abc"])
def test_section_id_validation_rejects_anything_that_is_not_a_section(bad):
    assert not SECTION_ID_RE.match(bad)


# --- extraction from the real articles --------------------------------------------------

def test_far_subsection_and_its_table_for_the_r_districts():
    sub = extract_subsection(_article("17-2-0300"), "17-2-0304-A")
    assert sub["heading"] == "Standards"
    assert sub["paragraphs"][0].startswith("17-2-0304-A Standards. All development in R districts")
    assert not any(p.startswith("17-2-0304-B") for p in sub["paragraphs"])  # stops at the next heading
    assert len(sub["tables"]) == 1 and "Maximum Floor Area Ratio" in sub["tables"][0]
    assert "Row 2: District: RS2; Maximum Floor Area Ratio*: 0.65" in sub["tables"][0]


def test_b_c_far_picks_the_standards_table_not_the_aro_table():
    sub = extract_subsection(_article("17-3-0400"), "17-3-0403-A")
    assert len(sub["tables"]) == 1
    assert "Proportion" not in sub["tables"][0].split("\n", 1)[0] and "Maximum Floor Area Ratio" in sub["tables"][0]


def test_a_section_level_id_includes_its_subsections():
    sub = extract_subsection(_article("17-2-0300"), "17-2-0304")
    heads = [p.split(" ", 1)[0] for p in sub["paragraphs"] if p.startswith("17-2-")]
    assert heads[:3] == ["17-2-0304", "17-2-0304-A", "17-2-0304-B"] and "17-2-0305" not in heads
    assert sub["tables"] == []  # a whole section has no single table to attach


def test_unknown_subsection_is_none():
    assert extract_subsection(_article("17-2-0300"), "17-2-0399-Z") is None
    assert extract_subsection("no headings here", "17-2-0304-A") is None


def test_every_cited_standard_resolves_to_its_text_and_table():
    """The sections Profile numbers cite (BULK_SECTIONS) must open on real text."""
    cited = {sec for fam in BULK_SECTIONS.values() for sec in fam.values() if sec}
    for sec in sorted(cited):
        sub = extract_subsection(_article(next(f for f in FILES if f == article_id(sec))), sec)
        assert sub is not None, sec
        assert sub["paragraphs"][0].startswith(sec + " "), sec
        if sec in TABLE_HINTS:
            assert sub["tables"], f"{sec} has a table hint but no table matched"


def test_table_hints_match_the_codes_real_column_headers():
    for sec, (include, exclude) in TABLE_HINTS.items():
        art = _article(next(f for f in FILES if f == article_id(sec)))
        cols = [b.split("\n", 1)[0] for b in art.split("\n[TABLE]\n")[1:]]
        hits = [c for c in cols if all(s in c for s in include) and not any(s in c for s in exclude)]
        assert hits, (sec, include)


# --- the endpoint -------------------------------------------------------------------------------

def _client():
    from unittest.mock import MagicMock
    with patch("backend.main.get_settings") as s, patch("backend.main.db") as db:
        s.return_value = MagicMock(anthropic_api_key="k", socrata_app_token="t", qdrant_url="http://localhost:6333",
                                   router_model="m", synthesizer_model="m", message_limit=10)
        db.init_db = AsyncMock()
        db.close_db = AsyncMock()
        db.count_user_messages = AsyncMock(return_value=0)
        yield TestClient(main.app)


@pytest.fixture
def client():
    yield from _client()


def _chunk(file: str) -> CodeChunk:
    return CodeChunk(text=_article(file), source_document="x", section=file, section_title="Bulk and density standards",
                     subsection=None, score=1.0, cross_references=[])


def test_endpoint_returns_the_subsection_with_the_codes_vintage(client):
    with patch.object(main, "get_full_section", new=AsyncMock(return_value=_chunk("17-2-0300"))) as fetch:
        r = client.get("/api/code/section/17-2-0304-A")
    assert r.status_code == 200
    d = r.json()
    fetch.assert_awaited_once_with("17-2-0300")  # asks for the article, not the subsection
    assert d["section_id"] == "17-2-0304-A" and d["article"] == "17-2-0300" and d["heading"] == "Standards"
    assert d["current_through"] == "2026-03-18" and d["vintage_label"] == "Council Journal of March 18, 2026"
    assert d["tables"] and "RS2" in d["tables"][0]


def test_endpoint_errors(client):
    assert client.get("/api/code/section/not-a-section").status_code == 422
    with patch.object(main, "get_full_section", new=AsyncMock(return_value=None)):
        assert client.get("/api/code/section/17-2-0304-A").status_code == 404
    with patch.object(main, "get_full_section", new=AsyncMock(return_value=_chunk("17-2-0300"))):
        assert client.get("/api/code/section/17-2-0399-Z").status_code == 404


def test_a_table_the_index_split_into_row_batches_is_put_back_together():
    text = (
        "17-2-0311-A Standards. Height limits:\n\n17-2-0311-B Exemptions. x"
        "\n\n[TABLE]\nColumns: District | Maximum Building Height (feet)\nRow 1: District: RS1; Maximum Building Height (feet): 30"
        "\n\n[TABLE]\nColumns: District | Maximum Building Height (feet)\nRow 2: District: RS2; Maximum Building Height (feet): 30"
        "\n\n[TABLE]\nColumns: District | Minimum Side Setback\nRow 1: District: RS1; Minimum Side Setback: 5"
    )
    sub = extract_subsection(text, "17-2-0311-A")
    assert len(sub["tables"]) == 1
    assert sub["tables"][0].splitlines() == [
        "Columns: District | Maximum Building Height (feet)",
        "Row 1: District: RS1; Maximum Building Height (feet): 30",
        "Row 2: District: RS2; Maximum Building Height (feet): 30",
    ]
