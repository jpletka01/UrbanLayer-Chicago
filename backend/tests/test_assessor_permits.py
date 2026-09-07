"""Tests for Cook County Assessor permit history (property/assessor_permits.py)."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.retrieval.property.assessor_permits import (
    MAX_ROWS,
    get_assessor_permits,
)

PIN = "17162260050000"


def _row(date, status="CLOSED", amount="50000.0", assessable="Non-Assessable",
         job="COMMERCIAL PERMIT", desc="INTERIOR ALTERATIONS"):
    r = {
        "date_issued": f"{date}T00:00:00.000",
        "status": status,
        "amount": amount,
        "job_code_primary": job,
        "work_description": desc,
    }
    if assessable is not None:
        r["assessable"] = assessable
    return r


def _patch(rows):
    return patch(
        "backend.retrieval.property.assessor_permits.socrata_get",
        new=AsyncMock(return_value=rows),
    )


@pytest.mark.asyncio
async def test_summarizes_recent_permits():
    rows = [
        _row("2026-06-26", status="PENDING", amount="89216.0"),
        _row("2026-06-22", status="PENDING", amount="500000.0"),
        _row("2024-11-01", status="CLOSED", amount="30000.0"),
    ]
    with _patch(rows):
        s = await get_assessor_permits(PIN)

    assert s is not None
    assert s.count == 3
    assert s.latest_date == "2026-06-26"
    assert s.total_declared_amount == 619216.0
    assert s.permits[0].status == "PENDING"
    assert s.permits[0].work_description == "INTERIOR ALTERATIONS"
    assert s.truncated is False


@pytest.mark.asyncio
async def test_flags_an_open_assessable_permit():
    """The point of the module: unclosed assessable work is a future tax change."""
    with _patch([_row("2026-06-22", status="PENDING", assessable="Assessable")]):
        s = await get_assessor_permits(PIN)
    assert s.assessable_pending is True
    assert s.permits[0].assessable is True


@pytest.mark.asyncio
async def test_closed_assessable_permit_is_not_pending():
    """Already-closed assessable work is baked into the assessment, not upcoming."""
    with _patch([_row("2023-01-05", status="CLOSED", assessable="Assessable")]):
        s = await get_assessor_permits(PIN)
    assert s.assessable_pending is False
    assert s.permits[0].assessable is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING", "OPEN", "RECHECK", "MANAGER REVIEW"])
async def test_every_live_status_counts_as_pending(status):
    with _patch([_row("2026-01-01", status=status, assessable="Assessable")]):
        s = await get_assessor_permits(PIN)
    assert s.assessable_pending is True, f"{status} should count as not-closed-out"


@pytest.mark.asyncio
async def test_missing_assessable_is_none_not_false():
    """~84k rows leave it blank; unknown must not read as 'not assessable'."""
    with _patch([_row("2026-01-01", assessable=None)]):
        s = await get_assessor_permits(PIN)
    assert s.permits[0].assessable is None
    assert s.assessable_pending is False


@pytest.mark.asyncio
async def test_filters_on_date_issued_never_the_junk_year_column():
    """`year` holds values like 2032 and is absent on ~84k rows — unusable."""
    mock = AsyncMock(return_value=[_row("2026-01-01")])
    with patch("backend.retrieval.property.assessor_permits.socrata_get", new=mock):
        await get_assessor_permits(PIN)

    params = mock.await_args.args[1]
    assert "date_issued >" in params["$where"]
    assert "year" not in params["$where"]
    assert params["$order"] == "date_issued DESC"


@pytest.mark.asyncio
async def test_queries_the_undashed_pin():
    """This dataset uses undashed 14-digit PINs, unlike most county sets."""
    mock = AsyncMock(return_value=[])
    with patch("backend.retrieval.property.assessor_permits.socrata_get", new=mock):
        await get_assessor_permits("17-16-226-005-0000")
    assert f"pin='{PIN}'" in mock.await_args.args[1]["$where"]


@pytest.mark.asyncio
async def test_marks_truncation_at_the_row_cap():
    with _patch([_row("2026-01-01") for _ in range(MAX_ROWS)]):
        s = await get_assessor_permits(PIN)
    assert s.truncated is True


@pytest.mark.asyncio
async def test_returns_none_when_no_permits_on_record():
    with _patch([]):
        assert await get_assessor_permits(PIN) is None


@pytest.mark.asyncio
async def test_survives_a_failed_lookup():
    with patch(
        "backend.retrieval.property.assessor_permits.socrata_get",
        new=AsyncMock(side_effect=RuntimeError("county down")),
    ):
        assert await get_assessor_permits(PIN) is None


@pytest.mark.asyncio
async def test_handles_unparseable_amount():
    with _patch([_row("2026-01-01", amount="n/a")]):
        s = await get_assessor_permits(PIN)
    assert s.permits[0].amount is None
    assert s.total_declared_amount is None


@pytest.mark.asyncio
async def test_caches_both_hit_and_miss():
    mock = AsyncMock(return_value=[])
    with patch("backend.retrieval.property.assessor_permits.socrata_get", new=mock):
        assert await get_assessor_permits(PIN) is None
        assert await get_assessor_permits(PIN) is None
    assert mock.await_count == 1


# --- Orchestrator wiring ---------------------------------------------------
#
# The property fan-out builds a POSITIONAL `coros` list and unpacks it with a
# hand-tracked `idx`. Appending to it is easy to get subtly wrong: a bad index
# silently assigns some OTHER source's result to assessor_permits (and shifts
# everything after it) with no error. These pin the wiring end to end.
#
# Everything in the fan-out that does I/O is stubbed. Two traps found the hard way:
# a chars=None commercial parcel drops into the phase-2 building-fallback fetches
# (real network), and `estimate_tax` opens an aiosqlite connection to ptaxsim whose
# worker thread keeps the interpreter alive at shutdown — the tests PASS and then the
# process hangs forever, which reads exactly like a hung test.

import contextlib  # noqa: E402

from backend.models import AssessorPermitSummary  # noqa: E402
from backend.retrieval.property import property_domain  # noqa: E402

_PARCEL = {
    "pin14": "17162260050000",
    "bldg_class": "5-17",
    "address": "300 S WACKER DR",
}


@contextlib.contextmanager
def _isolated_domain(*, permits, assessments=None):
    """property_domain with every I/O leaf stubbed except the permits lookup."""
    mock_permits = AsyncMock(return_value=permits)
    with patch("backend.retrieval.property.lookup_parcel",
               new=AsyncMock(return_value=_PARCEL)), \
         patch("backend.retrieval.property.get_characteristics",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.get_assessments",
               new=AsyncMock(return_value=assessments or [])), \
         patch("backend.retrieval.property.get_sales", new=AsyncMock(return_value=[])), \
         patch("backend.retrieval.property.appeals.get_appeals",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_geometry.get_parcel_geometry_facts",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_flags.get_parcel_flags",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property._fetch_building_fallbacks",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.tax_estimate.estimate_tax",
               new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.assessor_permits.get_assessor_permits",
               new=mock_permits):
        yield mock_permits


@pytest.mark.asyncio
async def test_summary_carries_assessor_permits_from_the_fan_out():
    summary = AssessorPermitSummary(count=2, assessable_pending=True, latest_date="2026-06-26")
    with _isolated_domain(permits=summary):
        result = await property_domain(41.8788, -87.6359, client=AsyncMock())

    assert result is not None
    assert result.assessor_permits is not None, "fan-out index lost the result"
    assert result.assessor_permits.count == 2
    assert result.assessor_permits.assessable_pending is True
    assert result.assessor_permits.latest_date == "2026-06-26"


@pytest.mark.asyncio
async def test_other_fields_still_land_after_the_appended_coro():
    """A wrong index would shift neighbours, not just drop the new field."""
    with _isolated_domain(
        permits=None,
        assessments=[{"year": "2024", "class": "517", "mailed_tot": "1000000"}],
    ):
        result = await property_domain(41.8788, -87.6359, client=AsyncMock())

    assert result.pin14 == "17162260050000"
    assert result.address == "300 S WACKER DR"
    assert result.total_assessed_value == 1000000
    assert result.assessor_permits is None


@pytest.mark.asyncio
async def test_report_path_skips_the_lookup():
    """`development_feasibility` skips the history block; permits ride with it."""
    with _isolated_domain(permits=AssessorPermitSummary(count=1)) as mock_permits:
        result = await property_domain(
            41.8788, -87.6359, client=AsyncMock(), workflow="development_feasibility",
        )

    assert mock_permits.await_count == 0
    assert result.assessor_permits is None
