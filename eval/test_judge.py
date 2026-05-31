"""Tests for the LLM-as-judge helper functions in run_eval.py."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from eval.run_eval import (
    DimensionScore,
    JudgeResult,
    _extract_metadata_flags,
    _extract_citations,
    _compute_overall_grade,
    _write_judge_json,
    _run_judge,
    Result,
    DIMENSIONS,
)


class TestExtractMetadataFlags:
    def test_full_context(self):
        ctx = {
            "code_chunks": [{"text": "section text", "section": "17-2-0300"}],
            "crime_last_90d": {"total": 100, "capped": True},
            "open_311_requests": {"total": 50, "capped": False},
            "permits": None,
            "violations": {"total": 10},
            "businesses": None,
            "requires_disclaimer": True,
            "parcel_zoning": {"zone_class": "B3-1"},
            "analytics": {"crime": []},
        }
        flags = _extract_metadata_flags(ctx)
        assert flags["has_code_chunks"] is True
        assert flags["num_code_chunks"] == 1
        assert "crime" in flags["data_sources_present"]
        assert "311" in flags["data_sources_present"]
        assert "violations" in flags["data_sources_present"]
        assert "permits" not in flags["data_sources_present"]
        assert "business" not in flags["data_sources_present"]
        assert flags["capped_sources"] == {"crime": True}
        assert flags["requires_disclaimer"] is True
        assert flags["has_parcel_zoning"] is True
        assert flags["has_analytics"] is True
        assert flags["has_crime_data"] is True

    def test_empty_context(self):
        flags = _extract_metadata_flags({})
        assert flags["has_code_chunks"] is False
        assert flags["num_code_chunks"] == 0
        assert flags["data_sources_present"] == []
        assert flags["capped_sources"] == {}
        assert flags["requires_disclaimer"] is False
        assert flags["has_parcel_zoning"] is False
        assert flags["has_analytics"] is False
        assert flags["has_crime_data"] is False

    def test_no_capped_sources(self):
        ctx = {
            "crime_last_90d": {"total": 100, "capped": False},
            "open_311_requests": {"total": 50},
        }
        flags = _extract_metadata_flags(ctx)
        assert flags["capped_sources"] == {}

    def test_multiple_code_chunks(self):
        ctx = {"code_chunks": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}
        flags = _extract_metadata_flags(ctx)
        assert flags["num_code_chunks"] == 3


class TestExtractCitations:
    def test_mixed_citations(self):
        answer = "Crime is up [data:crime] per [1] and [2]. See also [data:311]."
        cites = _extract_citations(answer)
        assert cites["code_citations"] == ["1", "2"]
        assert cites["data_citations"] == ["311", "crime"]

    def test_no_citations(self):
        cites = _extract_citations("No citations here.")
        assert cites["code_citations"] == []
        assert cites["data_citations"] == []

    def test_deduplicated(self):
        answer = "See [1] and [1] again, plus [data:crime] and [data:crime]."
        cites = _extract_citations(answer)
        assert cites["code_citations"] == ["1"]
        assert cites["data_citations"] == ["crime"]

    def test_high_index(self):
        answer = "References [1], [5], and [12]."
        cites = _extract_citations(answer)
        assert cites["code_citations"] == ["1", "12", "5"]


class TestComputeOverallGrade:
    def test_all_a(self):
        dims = [DimensionScore(d, "A", "") for d in DIMENSIONS]
        assert _compute_overall_grade(dims) == "A"

    def test_all_f(self):
        dims = [DimensionScore(d, "F", "") for d in DIMENSIONS]
        assert _compute_overall_grade(dims) == "F"

    def test_mixed_high(self):
        dims = [
            DimensionScore("citation_accuracy", "A", ""),
            DimensionScore("factuality", "A", ""),
            DimensionScore("completeness", "B", ""),
            DimensionScore("rule_compliance", "A", ""),
        ]
        # 4*0.3 + 4*0.3 + 3*0.2 + 4*0.2 = 3.8 -> round to 4 -> A
        assert _compute_overall_grade(dims) == "A"

    def test_mixed_mid(self):
        dims = [
            DimensionScore("citation_accuracy", "C", ""),
            DimensionScore("factuality", "C", ""),
            DimensionScore("completeness", "D", ""),
            DimensionScore("rule_compliance", "C", ""),
        ]
        # 2*0.3 + 2*0.3 + 1*0.2 + 2*0.2 = 1.8 -> round to 2 -> C
        assert _compute_overall_grade(dims) == "C"

    def test_borderline_rounds_up(self):
        dims = [
            DimensionScore("citation_accuracy", "B", ""),
            DimensionScore("factuality", "B", ""),
            DimensionScore("completeness", "A", ""),
            DimensionScore("rule_compliance", "A", ""),
        ]
        # 3*0.3 + 3*0.3 + 4*0.2 + 4*0.2 = 3.4 -> round to 3 -> B
        assert _compute_overall_grade(dims) == "B"

    def test_borderline_rounds_to_b(self):
        dims = [
            DimensionScore("citation_accuracy", "A", ""),
            DimensionScore("factuality", "B", ""),
            DimensionScore("completeness", "B", ""),
            DimensionScore("rule_compliance", "B", ""),
        ]
        # 4*0.3 + 3*0.3 + 3*0.2 + 3*0.2 = 3.3 -> round to 3 -> B
        assert _compute_overall_grade(dims) == "B"


class TestWriteJudgeJson:
    def test_output_structure(self, tmp_path):
        results = [
            JudgeResult(
                query_id="test_q1",
                question="What is X?",
                dimensions=[
                    DimensionScore("citation_accuracy", "A", "good cites"),
                    DimensionScore("factuality", "B", "mostly correct"),
                    DimensionScore("completeness", "A", "thorough"),
                    DimensionScore("rule_compliance", "A", "disclaimer present"),
                ],
                overall_grade="A",
                overall_reasoning="Strong answer",
            ),
            JudgeResult(
                query_id="test_q2",
                question="What is Y?",
                dimensions=[
                    DimensionScore("citation_accuracy", "C", "missing cite"),
                    DimensionScore("factuality", "C", "one error"),
                    DimensionScore("completeness", "D", "incomplete"),
                    DimensionScore("rule_compliance", "F", "no disclaimer"),
                ],
                overall_grade="D",
                overall_reasoning="Weak answer",
            ),
        ]
        out_path = tmp_path / "judge_results.json"
        _write_judge_json(results, skipped=2, model="claude-sonnet-4-6", path=out_path)

        data = json.loads(out_path.read_text())
        assert data["total_queries"] == 2
        assert data["skipped_queries"] == 2
        assert data["judge_model"] == "claude-sonnet-4-6"
        assert "timestamp" in data
        assert "last_run" in data
        assert data["overall_grade_distribution"]["A"] == 1
        assert data["overall_grade_distribution"]["D"] == 1
        assert len(data["per_query"]) == 2
        assert data["per_query"][0]["id"] == "test_q1"
        assert len(data["per_query"][0]["dimensions"]) == 4

    def test_avg_score(self, tmp_path):
        results = [
            JudgeResult("q1", "Q?", [DimensionScore(d, "A", "") for d in DIMENSIONS], "A", ""),
            JudgeResult("q2", "Q?", [DimensionScore(d, "F", "") for d in DIMENSIONS], "F", ""),
        ]
        out_path = tmp_path / "judge.json"
        _write_judge_json(results, 0, "model", out_path)
        data = json.loads(out_path.read_text())
        # A=1.0, F=0.0 -> avg 0.5
        assert data["avg_score"] == 0.5

    def test_dimension_summaries(self, tmp_path):
        results = [
            JudgeResult("q1", "Q?", [
                DimensionScore("citation_accuracy", "A", ""),
                DimensionScore("factuality", "B", ""),
                DimensionScore("completeness", "A", ""),
                DimensionScore("rule_compliance", "C", ""),
            ], "A", ""),
        ]
        out_path = tmp_path / "judge.json"
        _write_judge_json(results, 0, "model", out_path)
        data = json.loads(out_path.read_text())
        assert "citation_accuracy" in data["dimension_summaries"]
        assert data["dimension_summaries"]["citation_accuracy"]["avg_numeric"] == 4.0
        assert data["dimension_summaries"]["factuality"]["avg_numeric"] == 3.0


class TestRunJudge:
    @pytest.fixture
    def sample_result(self):
        return Result(
            id="test_q",
            question="What's the crime like in Wicker Park?",
            category="neighborhood_overview",
            passed=True,
            full_answer="Crime is moderate [data:crime]. Battery is the most common type.",
            context_dict={
                "code_chunks": [],
                "crime_last_90d": {"total": 150, "capped": False},
                "requires_disclaimer": False,
            },
        )

    @pytest.mark.asyncio
    async def test_successful_judge(self, sample_result):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = json.dumps({
            "dimensions": [
                {"dimension": "citation_accuracy", "grade": "A", "reasoning": "Valid data citation"},
                {"dimension": "factuality", "grade": "A", "reasoning": "Numbers match"},
                {"dimension": "completeness", "grade": "B", "reasoning": "Missing data lag note"},
                {"dimension": "rule_compliance", "grade": "A", "reasoning": "No rules applicable"},
            ],
            "overall_grade": "A",
            "overall_reasoning": "Strong answer overall",
        })
        mock_response.content = [mock_block]

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(return_value=mock_response)

            jr = await _run_judge(sample_result, "claude-sonnet-4-6")

        assert jr.query_id == "test_q"
        assert jr.overall_grade == "A"
        assert len(jr.dimensions) == 4
        assert jr.dimensions[0].grade == "A"

    @pytest.mark.asyncio
    async def test_unparseable_response(self, sample_result):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "This is not JSON"
        mock_response.content = [mock_block]

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(return_value=mock_response)

            jr = await _run_judge(sample_result, "claude-sonnet-4-6")

        assert jr.overall_grade == "F"
        assert "unparseable" in jr.overall_reasoning.lower()
        assert all(d.grade == "F" for d in jr.dimensions)

    @pytest.mark.asyncio
    async def test_api_failure(self, sample_result):
        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(side_effect=Exception("API down"))

            jr = await _run_judge(sample_result, "claude-sonnet-4-6")

        assert jr.overall_grade == "F"
        assert "failed" in jr.overall_reasoning.lower()

    @pytest.mark.asyncio
    async def test_missing_dimension_filled(self, sample_result):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = json.dumps({
            "dimensions": [
                {"dimension": "citation_accuracy", "grade": "A", "reasoning": "ok"},
                {"dimension": "factuality", "grade": "B", "reasoning": "ok"},
            ],
            "overall_grade": "B",
            "overall_reasoning": "Partial response",
        })
        mock_response.content = [mock_block]

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create = AsyncMock(return_value=mock_response)

            jr = await _run_judge(sample_result, "claude-sonnet-4-6")

        dim_names = {d.dimension for d in jr.dimensions}
        for expected in DIMENSIONS:
            assert expected in dim_names

    @pytest.mark.asyncio
    async def test_truncates_long_chunks(self, sample_result):
        sample_result.context_dict = {
            "code_chunks": [{"text": "x" * 1000, "section": "17-2-0300"}],
        }

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = json.dumps({
            "dimensions": [{"dimension": d, "grade": "A", "reasoning": ""} for d in DIMENSIONS],
            "overall_grade": "A",
            "overall_reasoning": "",
        })
        mock_response.content = [mock_block]

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            create_mock = AsyncMock(return_value=mock_response)
            instance.messages.create = create_mock

            await _run_judge(sample_result, "claude-sonnet-4-6")

        call_args = create_mock.call_args
        user_content = call_args.kwargs["messages"][0]["content"]
        assert "[truncated]" in user_content
