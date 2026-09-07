"""The parser's section-id write-gate.

`SECTION_ID_RE` gates which parsed sections are written to disk (and so reach the
index). It was `\\d+-\\d+-\\d+`, which silently dropped all 872 Title-14 sections --
the entire Chicago building code -- as "non-section", even though SECTION_RE matched
them. These pin the shapes that must pass so it can't narrow again unnoticed.
"""

from __future__ import annotations

import pytest

from ingestion.parse_chicago_code import SECTION_ID_RE, SECTION_RE


@pytest.mark.parametrize("section_id", [
    "2-120-740",       # plain municipal code (Landmarks)
    "17-3-0104",       # zoning, leading-zero segment
    "13-12-020",
    "4-6-100.1",       # single decimal suffix
    "14A-1-101",       # building code: lettered title volume
    "14B-3-303",
    "14E-2-201",
    "14X-1-100",
    "14N-C1-C001",     # energy code, commercial: lettered chapter AND section
    "14N-C4-C402",
    "14N-R4-R402",     # energy code, residential
    "14N-R7-R700",
])
def test_gate_admits_real_section_ids(section_id):
    assert SECTION_ID_RE.fullmatch(section_id), f"{section_id} must be indexable"


@pytest.mark.parametrize("junk", [
    "",
    "TITLE 14A",
    "CHAPTER 14A-1",
    "ARTICLE II",
    "foo-bar-baz",
    "14A-1",           # too few segments
])
def test_gate_rejects_non_sections(junk):
    assert not SECTION_ID_RE.fullmatch(junk)


def test_gate_is_at_least_as_permissive_as_the_parser_regex():
    """A section SECTION_RE extracts must not then be dropped by the gate.

    That mismatch is exactly the bug: SECTION_RE was widened for Title 14 and the
    gate was not, so 872 sections parsed cleanly and were thrown away.
    """
    for section_id in ["14A-1-101", "17-3-0104", "2-120-740", "4-6-100.1"]:
        m = SECTION_RE.match(f"{section_id} Some heading text")
        assert m and m.group(1) == section_id
        assert SECTION_ID_RE.fullmatch(m.group(1))


def test_gate_covers_every_title_14_volume():
    """Title 14 ships as eleven lettered volumes; all must be indexable."""
    volumes = ["14A", "14B", "14C", "14E", "14F", "14G", "14M", "14N", "14P", "14R", "14X"]
    for vol in volumes:
        assert SECTION_ID_RE.fullmatch(f"{vol}-1-101"), f"{vol} volume must be indexable"



class TestManifestContentHash:
    """The manifest hash gates incremental re-embedding.

    NOTE: `section_title` is deliberately NOT hashed. It reaches the index (it is stored
    on the Qdrant payload), so a heading-only fix is a silent no-op — the diff reports
    "0 modified" and the stale title stays indexed. That was hit for real on 2026-09-07
    (50 Energy-Code sections). Adding it to the hash was tried and REVERTED: it
    invalidates every existing hash, which forces a full 9,487-section re-embed and
    trips the zoning-cache staleness check for 147 Title-17 sections that did not
    actually change — and rebuilding that cache requires RERANKER_ENABLED=true, which
    is off by design after the OOM incident. The cost lands on prod ops for a rare edge
    case, so the gap is documented in known-issues.md instead. These tests pin the
    CURRENT behavior; flip the last one if that tradeoff is ever revisited.
    """

    def test_body_change_is_detected(self):
        from ingestion.manifest import _content_hash
        a = {"body_paragraphs": ["one"], "tables": [], "section_title": "T"}
        b = {"body_paragraphs": ["two"], "tables": [], "section_title": "T"}
        assert _content_hash(a) != _content_hash(b)

    def test_table_change_is_detected(self):
        from ingestion.manifest import _content_hash
        a = {"body_paragraphs": ["x"], "tables": [], "section_title": "T"}
        b = {"body_paragraphs": ["x"], "tables": [{"rows": [[1]]}], "section_title": "T"}
        assert _content_hash(a) != _content_hash(b)

    def test_hash_is_stable_for_identical_input(self):
        from ingestion.manifest import _content_hash
        d = {"body_paragraphs": ["x"], "tables": [], "section_title": "T"}
        assert _content_hash(d) == _content_hash(dict(d))

    def test_section_title_is_not_hashed_documented_gap(self):
        """Documents the known gap above — NOT an endorsement of it."""
        from ingestion.manifest import _content_hash
        a = {"body_paragraphs": ["x"], "tables": [], "section_title": ""}
        b = {"body_paragraphs": ["x"], "tables": [], "section_title": "Building envelope"}
        assert _content_hash(a) == _content_hash(b), (
            "if this now differs, the hash was widened — see known-issues.md and drop "
            "the workaround note there"
        )
