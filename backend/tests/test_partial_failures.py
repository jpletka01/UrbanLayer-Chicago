"""WS6 M7: partial failures, shown honestly.

One table names what failed (``data_health/failures.py``); the Profile's modules, the chat footer and the report's
sections read it. The app counts its own calls to each source and the checker turns a high failure rate into a
warn or an alarm (``data_health/live.py``). ``DATA_HEALTH_FAULT`` forces a source to fail so every surface can
be seen saying "couldn't check", and none saying "no".
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.chat_sources import build_sources_footer
from backend.data_health import failures, live
from backend.data_health.evaluate import ProbeResult, evaluate
from backend.data_health.registry import BY_ID, SOURCES
from backend.main import render_report_html
from backend.models import ContextObject, RegulatorySummary, ReportData, ZoningSummary
from backend.report_builder import _apply_mock_overrides

REPO = Path(__file__).resolve().parents[2]
GAP = "landmark designation (City zoning map didn't answer)"
NOW = datetime(2026, 10, 22, 15, 30, tzinfo=timezone.utc)


# --- the table ------------------------------------------------------------------------------------------------

def test_every_label_a_retrieval_path_can_emit_resolves_to_a_key():
    for key, label in failures.LABELS.items():
        assert failures.key_for_label(label) == key, key
    assert failures.key_for_label(GAP) == "regulatory"
    assert failures.key_for_label("regulatory overlays (City zoning map didn't answer)") == "regulatory"
    for gap in ("property characteristics", "property assessments", "property tax estimate"):
        assert failures.key_for_label(gap) == "property"
    assert failures.key_for_label("something nobody named") is None


def test_a_retrieval_task_is_labelled_the_same_in_every_path():
    assert failures.label("zoning_lookup") == failures.label("zoning") == "parcel zoning"
    assert failures.label("comparable_sales") == failures.label("comparables") == "comparable sales"
    assert failures.label("crime") == "crime statistics"


def test_detail_keeps_the_words_that_reported_each_failure():
    got = failures.failed_detail(["property assessments", "property tax estimate", GAP, "crime statistics", "crime statistics", "???"])
    assert got == [
        {"key": "property", "labels": ["property assessments", "property tax estimate"]},
        {"key": "regulatory", "labels": [GAP]},
        {"key": "crime", "labels": ["crime statistics"]},
    ]
    assert failures.failed_keys(["property assessments", GAP]) == ["property", "regulatory"]


def test_every_key_belongs_to_a_module_and_the_profile_table_says_the_same():
    assert set(failures.LABELS) == set(failures.MODULES)
    ts = (REPO / "frontend" / "src" / "lib" / "failedSources.ts").read_text()
    body = ts[ts.index("MODULE_OF"):ts.index("};")]
    fe = dict(re.findall(r'"?(\w+)"?:\s*"(\w+)"', body))
    assert fe == failures.MODULES


# --- live failure rates ---------------------------------------------------------------------------------------

def test_counts_flush_into_the_hour_and_read_back_over_a_window(tmp_path):
    db = tmp_path / "live.db"
    for _ in range(8):
        live.record("chi.crime", True)
    for _ in range(4):
        live.record("chi.crime", False)
    live.record("chi.311", True)
    assert live.pending()["chi.crime"] == (12, 4)
    assert live.flush(db, now=NOW) == 2 and live.pending() == {}
    live.record("chi.crime", False)
    live.flush(db, now=NOW + timedelta(minutes=10))  # same hour: added to the row, not a second one
    got = live.read_window(db, now=NOW + timedelta(hours=1))
    assert got["chi.crime"] == (13, 5) and got["chi.311"] == (1, 0)
    # a source that was not called in the window is absent, and an old hour is outside it
    assert live.read_window(db, now=NOW + timedelta(hours=30)) == {}


def test_an_unknown_source_id_is_dropped_not_stored(tmp_path):
    db = tmp_path / "live.db"
    live.record("not.a.source", False)
    live.record(None, False)
    assert live.flush(db, now=NOW) == 0 and not db.exists()


def test_a_failed_flush_keeps_the_counts_for_the_next_one(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory")  # the database path cannot be created under a file
    live.record("chi.crime", False)
    live.record("chi.crime", True)
    assert live.flush(blocker / "live.db", now=NOW) == 0
    assert live.pending()["chi.crime"] == (2, 1)  # nothing lost
    assert live.flush(tmp_path / "live.db", now=NOW) == 1  # the next flush writes it
    assert live.read_window(tmp_path / "live.db", now=NOW) == {"chi.crime": (2, 1)}


def test_old_rows_are_pruned(tmp_path):
    db = tmp_path / "live.db"
    live.record("chi.crime", True)
    live.flush(db, now=NOW - timedelta(days=live.RETENTION_DAYS + 2))
    live.record("chi.311", True)
    live.flush(db, now=NOW)
    with sqlite3.connect(db) as con:
        assert [r[0] for r in con.execute("SELECT source_id FROM live_calls")] == ["chi.311"]


@pytest.mark.parametrize("attempts,failures_,want", [
    (9, 9, None),            # too few calls to say anything
    (10, 2, None),           # 20% exactly: not over
    (10, 3, "warn"),
    (100, 21, "warn"),
    (100, 50, "warn"),       # 50% exactly: not over
    (100, 51, "alarm"),
    (10, 10, "alarm"),
    (50, 0, None),
])
def test_the_rate_thresholds(attempts, failures_, want):
    got = live.rate_finding(attempts, failures_)
    assert (got[0] if got else None) == want
    if got:
        assert f"{failures_} of {attempts}" in got[1]


def _spec(source_id: str = "chi.crime"):
    return BY_ID[source_id]


def test_the_checker_turns_a_failing_source_into_a_warn_or_an_alarm_even_when_the_probe_is_fine():
    probe = ProbeResult(published=date(2026, 10, 21), content=date(2026, 10, 20))
    today = date(2026, 10, 22)
    base = evaluate(_spec(), probe, today)
    assert base.state == "ok"
    warn = evaluate(_spec(), probe, today, live=(50, 15))
    assert warn.state == "warn" and "15 of 50 live calls failed" in warn.reason
    assert evaluate(_spec(), probe, today, live=(50, 40)).state == "alarm"
    assert evaluate(_spec(), probe, today, live=(5, 5)).state == "ok"  # under 10 calls: no claim
    assert evaluate(_spec(), probe, today, live=None).state == "ok"


@pytest.mark.asyncio
async def test_run_all_reads_the_apps_live_counts(tmp_path, monkeypatch):
    from backend.data_health import check

    live.record("chi.crime", False)
    for _ in range(11):
        live.record("chi.crime", False)
    live.flush(live.DB_FILE, now=datetime.now(timezone.utc))
    spec = _spec()
    rows, _ = await check.run_all((spec,), today=date.today(), overrides={spec.id: ProbeResult(published=date.today(), content=date.today())})
    assert rows[0].status.state == "alarm" and "live calls failed" in rows[0].status.reason


# --- socrata: the outcome is counted once, and the flag forces a failure --------------------------------------------

CRIME_DATASET = next(s.locator.split(":", 1)[1] for s in SOURCES if s.id == "chi.crime")


@pytest.mark.asyncio
async def test_a_socrata_call_counts_once_whatever_the_retries():
    from backend.retrieval.socrata import SocrataError, socrata_get

    ok = MagicMock(status_code=200, json=MagicMock(return_value=[{"a": 1}]), raise_for_status=MagicMock())
    client = MagicMock(get=AsyncMock(return_value=ok))
    assert await socrata_get(CRIME_DATASET, {"$limit": 1}, client=client) == [{"a": 1}]
    assert live.pending()["chi.crime"] == (1, 0)

    boom = MagicMock(status_code=503, request=MagicMock(), raise_for_status=MagicMock())
    client = MagicMock(get=AsyncMock(return_value=boom))
    from unittest.mock import patch

    with patch("backend.retrieval.socrata.asyncio.sleep", new=AsyncMock()), pytest.raises(SocrataError):
        await socrata_get(CRIME_DATASET, {"$limit": 1}, client=client)
    assert client.get.await_count == 3 and live.pending()["chi.crime"] == (2, 1)  # three attempts, one failed call


@pytest.mark.asyncio
async def test_the_fault_flag_forces_a_socrata_dataset_or_a_whole_source_to_fail(monkeypatch):
    from backend.retrieval.socrata import SocrataError, socrata_get

    client = MagicMock(get=AsyncMock())
    for spec in (f"socrata:{CRIME_DATASET}", "source:chi.crime"):
        monkeypatch.setenv("DATA_HEALTH_FAULT", spec)
        with pytest.raises(SocrataError, match="forced by DATA_HEALTH_FAULT"):
            await socrata_get(CRIME_DATASET, {"$limit": 1}, client=client)
    client.get.assert_not_awaited()
    monkeypatch.setenv("DATA_HEALTH_FAULT", "socrata:some-other-dataset")
    ok = MagicMock(status_code=200, json=MagicMock(return_value=[]), raise_for_status=MagicMock())
    client.get = AsyncMock(return_value=ok)
    assert await socrata_get(CRIME_DATASET, {"$limit": 1}, client=client) == []


def test_the_fault_flag_parses_several_and_is_ignored_in_production(monkeypatch):
    monkeypatch.setenv("DATA_HEALTH_FAULT", "overlay:5,6;source:chi.crime ; socrata:abcd-1234")
    assert live.fault_ids("overlay") == {"5", "6"} and live.fault_ids("socrata") == {"abcd-1234"}
    assert live.fault("overlay", 6) and not live.fault("overlay", 7)
    assert live.fault("socrata", "x", source_id="chi.crime")  # the source-level switch
    monkeypatch.setattr("backend.config.get_settings", lambda: MagicMock(environment="production"))
    assert live.fault_ids("overlay") == set() and not live.fault("overlay", 5)


# --- overlays: the flag, the counters, the tri-state --------------------------------------------------------------------

def _clear_response():
    return MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value={"features": []}))


@pytest.mark.asyncio
async def test_a_forced_overlay_layer_is_failed_not_clear_and_is_not_cached(monkeypatch):
    from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS, query_overlays_checked

    monkeypatch.setenv("DATA_HEALTH_FAULT", "overlay:5")
    client = MagicMock(get=AsyncMock(return_value=_clear_response()))
    out = await query_overlays_checked(41.9, -87.68, client=client)
    assert out.failed == [5] and out.hits == []
    assert client.get.await_count == len(OVERLAY_LAYERS) - 1  # the forced layer never reached the network
    monkeypatch.delenv("DATA_HEALTH_FAULT")
    again = await query_overlays_checked(41.9, -87.68, client=client)  # a failure was not served from the cache
    assert again.failed == []


# --- the chat footer says it, whatever the model does ---------------------------------------------------------------

def test_chat_footer_says_what_couldnt_be_checked_after_the_sources():
    prov = {"area.crime": {"label": "x", "query_date": "2026-10-22", "source_id": "chi.crime", "as_of": "2026-10-14",
                           "as_of_basis": "period_end", "geography": "West Town", "scope": "community_area",
                           "confidence": "standard", "confidence_reasons": []}}
    footer = build_sources_footer(prov, [], None, None, [GAP, "property records"])
    assert footer.index("Sources for the data used") < footer.index("**Couldn't check today:**")
    assert GAP in footer and "property records" in footer and "not the same as none on record" in footer
    assert "not a landmark" not in footer.lower()


def test_chat_footer_with_only_failures_is_just_the_notice():
    footer = build_sources_footer({}, [], None, None, ["crime statistics"])
    assert footer.startswith("\n\n---\n**Couldn't check today:** crime statistics.") and "Sources for" not in footer
    assert build_sources_footer({}, [], None, None, []) == "" and build_sources_footer({}, [], None, None, None) == ""


# --- the report: the cover and the section ------------------------------------------------------------------------------

def _report(**over) -> ReportData:
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"),
                        regulatory=RegulatorySummary(unchecked_overlays=["landmark_building"], data_gaps=[GAP]))
    r = _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", context=ctx, resolved_pin="14313320180000", resolved_confidence="authoritative"))
    for k, v in over.items():
        setattr(r, k, v)
    return r


def _section(page: str, anchor: str) -> str:
    i = page.index(f'id="{anchor}"')
    return page[i:i + 1500]


def test_a_report_section_that_left_a_source_out_says_so_at_its_head():
    page = render_report_html(_report(partial_failures=["comparable sales", "property tax estimate", "building violations"]), "en", report_date="October 22, 2026")
    market = _section(page, "section-market")
    assert 'data-testid="section-unchecked"' in market and "comparable sales" in market and "not the same as none on record" in market
    assert "property tax estimate" in _section(page, "section-property")
    assert "building violations" in _section(page, "section-site-condition")
    # a section whose sources answered says nothing
    assert 'data-testid="section-unchecked"' not in _section(page, "section-zoning")
    # and the cover lists all of it
    cover = page[: page.index("TABLE OF CONTENTS")]
    assert "Not checked in this report: comparable sales, property tax estimate, building violations" in cover


def test_a_clean_report_has_no_unchecked_notice():
    page = render_report_html(_report(), "en", report_date="October 22, 2026")
    assert 'data-testid="section-unchecked"' not in page
    assert "Not checked in this report" not in page


def test_a_forced_overlay_failure_is_unknown_on_the_report_never_not_a_landmark():
    page = render_report_html(_report(partial_failures=[GAP]), "en", report_date="October 22, 2026")
    assert "landmark" in page.lower() and "Couldn&#39;t check" in page
    assert "No overlay or special districts detected" not in page


# --- core property calls: a failed call is a gap, never "none on record", and is not cached ------------------------------

@pytest.mark.asyncio
async def test_the_property_domain_reports_a_gap_for_each_failed_core_call():
    from unittest.mock import patch

    from backend.retrieval.property import property_domain
    from backend.tests.test_property_orchestrator import SAMPLE_PARCEL

    boom = AsyncMock(side_effect=Exception("Socrata down"))
    with patch("backend.retrieval.property.lookup_parcel", new=AsyncMock(return_value=SAMPLE_PARCEL)), \
         patch("backend.retrieval.property.get_characteristics", new=boom), \
         patch("backend.retrieval.property.get_assessments", new=boom), \
         patch("backend.retrieval.property.get_sales", new=boom), \
         patch("backend.retrieval.property.tax_estimate.estimate_tax", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.appeals.get_appeals", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_flags.get_parcel_flags", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.assessor_permits.get_assessor_permits", new=AsyncMock(return_value=None)):
        summary = await property_domain(41.93, -87.64, client=AsyncMock())
    assert {"property characteristics", "property assessments", "property sales history"} <= set(summary.data_gaps)
    assert {"property characteristics", "property assessments", "property sales history"} <= set(summary.failed_calls)
    assert failures.failed_detail(summary.data_gaps)[0]["key"] == "property"


@pytest.mark.asyncio
async def test_a_record_the_source_does_not_have_is_a_gap_but_not_a_failed_call():
    """An exempt parcel has no assessments or tax bill: those are gaps, but nothing failed, so the Profile
    does not say "couldn't check" for them."""
    from unittest.mock import patch

    from backend.retrieval.property import property_domain
    from backend.tests.test_property_orchestrator import SAMPLE_PARCEL

    with patch("backend.retrieval.property.lookup_parcel", new=AsyncMock(return_value=SAMPLE_PARCEL)), \
         patch("backend.retrieval.property.get_characteristics", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.get_assessments", new=AsyncMock(return_value=[])), \
         patch("backend.retrieval.property.get_sales", new=AsyncMock(return_value=[])), \
         patch("backend.retrieval.property.tax_estimate.estimate_tax", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.appeals.get_appeals", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_flags.get_parcel_flags", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.assessor_permits.get_assessor_permits", new=AsyncMock(return_value=None)):
        summary = await property_domain(41.93, -87.64, client=AsyncMock())
    assert "property assessments" in summary.data_gaps
    assert summary.failed_calls == []


@pytest.mark.asyncio
async def test_a_failed_comparable_sales_query_raises_and_is_not_cached():
    from unittest.mock import patch

    from backend.retrieval.property import sales

    boom = AsyncMock(side_effect=Exception("Socrata down"))
    with patch("backend.retrieval.property.sales.socrata_get", new=boom):
        with pytest.raises(Exception, match="Socrata down"):
            await sales.nearby_comparable_sales(41.9, -87.68, "5")
    assert boom.await_count >= 1
    # the failure was not remembered as "no comps nearby": a retry reaches the source again
    calls = boom.await_count
    with patch("backend.retrieval.property.sales.socrata_get", new=AsyncMock(return_value=[])) as ok:
        assert (await sales.nearby_comparable_sales(41.9, -87.68, "5"))["sales"] == []
    assert ok.await_count >= 1 and boom.await_count == calls
