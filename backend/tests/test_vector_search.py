import asyncio

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.retrieval.vector_search import (
    _payload_to_chunk,
    expand_cross_references,
    get_by_section_ids_batch,
    MAX_CROSS_REF_PER_CHUNK,
    _SECTION_REF_RE,
)
from backend.models import CodeChunk


class TestPayloadToChunk:
    def test_converts_full_payload(self):
        payload = {
            "text": "Coach houses are permitted in RS-3 districts.",
            "source_document": "Chicago Municipal Code",
            "section": "17-2-0303",
            "section_title": "Detached Houses",
            "subsection": "(a)(3)",
            "cross_references": ["17-2-0200", "17-10-0207"],
        }
        chunk = _payload_to_chunk(payload, score=0.92)

        assert chunk.text == "Coach houses are permitted in RS-3 districts."
        assert chunk.section == "17-2-0303"
        assert chunk.section_title == "Detached Houses"
        assert chunk.subsection == "(a)(3)"
        assert chunk.score == 0.92
        assert chunk.cross_references == ["17-2-0200", "17-10-0207"]

    def test_handles_missing_fields(self):
        payload = {"text": "Some text", "section": "1-1-1"}
        chunk = _payload_to_chunk(payload, score=0.5)

        assert chunk.text == "Some text"
        assert chunk.section == "1-1-1"
        assert chunk.section_title == ""
        assert chunk.subsection is None
        assert chunk.cross_references == []

    def test_handles_null_cross_references(self):
        payload = {"text": "Text", "section": "1-1-1", "cross_references": None}
        chunk = _payload_to_chunk(payload, score=0.5)
        assert chunk.cross_references == []

    def test_filters_cross_refs_against_known_sections(self):
        known = frozenset({"17-2-0200"})
        payload = {
            "text": "Text",
            "section": "17-2-0303",
            "cross_references": ["17-2-0200", "17-10-0207", "Ch.17-2"],
        }
        chunk = _payload_to_chunk(payload, score=0.9, known_sections=known)
        assert chunk.cross_references == ["17-2-0200"]


class TestSectionRefRegex:
    def test_matches_valid_section_ids(self):
        assert _SECTION_REF_RE.match("17-2-0303")
        assert _SECTION_REF_RE.match("17-10-0207")
        assert _SECTION_REF_RE.match("1-1-1")
        assert _SECTION_REF_RE.match("17-2-0303.5")
        assert _SECTION_REF_RE.match("14A-1-104")
        assert _SECTION_REF_RE.match("14A-3-301.2.2")

    def test_rejects_invalid_section_ids(self):
        assert not _SECTION_REF_RE.match("Title17")
        assert not _SECTION_REF_RE.match("Ch.17-2")
        assert not _SECTION_REF_RE.match("Section 17")
        assert not _SECTION_REF_RE.match("17-2")
        assert not _SECTION_REF_RE.match("")


class TestExpandCrossReferences:
    @pytest.fixture
    def base_chunk(self):
        return CodeChunk(
            text="Primary chunk about zoning.",
            source_document="Chicago Municipal Code",
            section="17-2-0303",
            section_title="Detached Houses",
            score=0.9,
            cross_references=["17-10-0207", "17-2-0200"],
        )

    def _make_chunk(self, section_id, text="Ref text"):
        return CodeChunk(
            text=text,
            source_document="CMC",
            section=section_id,
            section_title="Ref",
            score=1.0,
        )

    def test_expands_valid_section_refs(self, base_chunk):
        batch = {
            "17-10-0207": self._make_chunk("17-10-0207", "Referenced parking requirements."),
            "17-2-0200": self._make_chunk("17-2-0200"),
        }

        async def mock_batch(ids):
            return batch

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([base_chunk]))

        assert len(result) == 3
        assert result[0].section == "17-2-0303"
        ref_sections = {c.section for c in result[1:]}
        assert "17-10-0207" in ref_sections

    def test_dedupes_already_present_sections(self, base_chunk):
        existing_chunk = CodeChunk(
            text="Already present.",
            source_document="Chicago Municipal Code",
            section="17-10-0207",
            section_title="Parking",
            score=0.85,
        )

        async def mock_batch(ids):
            assert "17-10-0207" not in ids
            return {"17-2-0200": self._make_chunk("17-2-0200")}

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([base_chunk, existing_chunk]))

        sections = [c.section for c in result]
        assert sections.count("17-10-0207") == 1
        assert "17-2-0200" in sections

    def test_skips_non_section_refs(self):
        chunk_with_title_ref = CodeChunk(
            text="References a title.",
            source_document="CMC",
            section="17-2-0100",
            section_title="Test",
            score=0.8,
            cross_references=["Title17", "Ch.17-2", "17-3-0200"],
        )

        captured_ids = []

        async def mock_batch(ids):
            captured_ids.extend(ids)
            return {"17-3-0200": self._make_chunk("17-3-0200", "Valid section.")}

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([chunk_with_title_ref]))

        assert captured_ids == ["17-3-0200"]
        assert len(result) == 2

    def test_caps_cross_refs_per_chunk(self):
        chunk_with_many_refs = CodeChunk(
            text="Many references.",
            source_document="CMC",
            section="17-1-0100",
            section_title="Test",
            score=0.9,
            cross_references=[f"17-1-{i:04d}" for i in range(10)],
        )

        batch = {f"17-1-{i:04d}": self._make_chunk(f"17-1-{i:04d}") for i in range(10)}
        captured_ids = []

        async def mock_batch(ids):
            captured_ids.extend(ids)
            return batch

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([chunk_with_many_refs]))

        assert len(captured_ids) == MAX_CROSS_REF_PER_CHUNK
        assert len(result) == 1 + MAX_CROSS_REF_PER_CHUNK

    def test_sets_reduced_score_on_expanded_refs(self, base_chunk):
        batch = {
            "17-10-0207": self._make_chunk("17-10-0207", "Referenced chunk."),
            "17-2-0200": self._make_chunk("17-2-0200"),
        }

        async def mock_batch(ids):
            return batch

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([base_chunk]))

        expanded = [c for c in result if c.section == "17-10-0207"][0]
        assert expanded.score == 0.5

    def test_handles_missing_reference(self, base_chunk):
        async def mock_batch(ids):
            return {}

        with patch("backend.retrieval.vector_search.get_by_section_ids_batch", side_effect=mock_batch):
            result = asyncio.run(expand_cross_references([base_chunk]))

        assert len(result) == 1
        assert result[0].section == "17-2-0303"
