"""The evaluation rules (WS6 plan §3.4), table-driven over synthetic specs."""

import asyncio
from dataclasses import replace
from datetime import date

import pytest

from backend.data_health import check
from backend.data_health.evaluate import Finding, ProbeError, ProbeResult, evaluate
from backend.data_health.registry import Ack, Content, Contract, Frozen, SourceSpec

TODAY = date(2026, 10, 21)

BASE = SourceSpec(
    id="test.source", name="Test", publisher="Test", tier="official_record", kind="socrata", locator="city:abcd-1234",
    owner_modules=("backend/config.py",), warn_days=10, alarm_days=30,
)


def spec(**kw) -> SourceSpec:
    return replace(BASE, **kw)


def ago(days: int) -> date:
    return date.fromordinal(TODAY.toordinal() - days)


@pytest.mark.parametrize(
    "age,state",
    [(0, "ok"), (10, "ok"), (11, "warn"), (30, "warn"), (31, "alarm"), (-5, "ok")],  # a future date is not stale
)
def test_age_against_warn_and_alarm_days(age, state):
    assert evaluate(spec(), ProbeResult(published=ago(age)), TODAY).state == state


def test_content_date_beats_publish_date():
    """The publisher touching a dataset is not the data being current (principle 1)."""
    s = evaluate(spec(), ProbeResult(published=ago(0), content=ago(40)), TODAY)
    assert s.state == "alarm" and s.basis == "content" and s.age_days == 40
    assert evaluate(spec(), ProbeResult(published=ago(40), content=ago(0)), TODAY).state == "ok"


def test_no_date_signal_is_unknown_not_red():
    assert evaluate(spec(), ProbeResult(), TODAY).state == "unknown"
    s = evaluate(spec(warn_days=None, alarm_days=None, contract=Contract(layer_name="X")), ProbeResult(layer_name="X"), TODAY)
    assert s.state == "unknown" and "structure" in s.reason


def test_availability_only_source_is_ok_when_it_answers():
    s = spec(warn_days=None, alarm_days=None, availability_only=True)
    assert evaluate(s, ProbeResult(info="known answer within 4 m"), TODAY).state == "ok"
    assert evaluate(s, ProbeResult(findings=[Finding("error", "wrong answer")]), TODAY).state == "error"


# --- frozen: alarm on change, not on age --------------------------------------------------------

def test_frozen_source_is_ok_while_unchanged_however_old():
    s = spec(warn_days=None, alarm_days=None, frozen=Frozen("2015-08-15", "footprints from 2015"))
    assert evaluate(s, ProbeResult(published=date(2015, 8, 15)), TODAY).state == "frozen_ok"


def test_frozen_source_that_changes_alarms():
    s = spec(warn_days=None, alarm_days=None, frozen=Frozen("2015-08-15", "footprints from 2015"))
    st = evaluate(s, ProbeResult(published=date(2026, 9, 1)), TODAY)
    assert st.state == "alarm" and "frozen source changed" in st.reason and "2026-09-01" in st.reason


def test_frozen_artifact_with_no_probe_is_frozen_ok():
    assert evaluate(spec(frozen=Frozen("1996", "1996 survey")), None, TODAY).state == "frozen_ok"


def test_no_probe_yet_is_unknown_and_says_why():
    st = evaluate(spec(note="Lands in WS6 M4."), None, TODAY)
    assert st.state == "unknown" and "Lands in WS6 M4" in st.reason


# --- the year-lag comparison (ACS community areas vs the Census release) -------------------------

@pytest.mark.parametrize("content,reference,state", [(2024, 2024, "ok"), (2023, 2024, "warn"), (2022, 2024, "alarm")])
def test_year_lag_against_a_reference_release(content, reference, state):
    s = spec(warn_days=None, alarm_days=None, content=Content("max_year", "acs_year", reference="census_latest_release"))
    assert evaluate(s, ProbeResult(content_year=content, reference_year=reference), TODAY).state == state


def test_year_lag_with_no_reference_is_unknown():
    s = spec(warn_days=None, alarm_days=None, content=Content("max_year", "acs_year", reference="census_latest_release"))
    assert evaluate(s, ProbeResult(content_year=2023), TODAY).state == "unknown"


# --- contract: the worst of date and contract wins -----------------------------------------------

def test_contract_failures_are_errors_and_beat_a_fresh_date():
    s = spec(contract=Contract(required_fields=("ZONE_CLASS", "CLERK_URL"), layer_name="Zoning Boundaries", count_band=(100, 200)))
    ok = ProbeResult(published=ago(0), layer_name="Zoning Boundaries", fields=("ZONE_CLASS", "CLERK_URL"), count=150)
    assert evaluate(s, ok, TODAY).state == "ok"
    renamed = replace(ok, layer_name="Landmark Buildings")
    st = evaluate(s, renamed, TODAY)
    assert st.state == "error" and "Landmark Buildings" in st.reason
    assert evaluate(s, replace(ok, fields=("ZONE_CLASS",)), TODAY).state == "error"
    assert evaluate(s, replace(ok, count=900), TODAY).state == "alarm"


def test_a_stale_date_and_a_broken_contract_report_both():
    s = spec(contract=Contract(layer_name="A"))
    st = evaluate(s, ProbeResult(published=ago(60), layer_name="B"), TODAY)
    assert st.state == "error" and "days old" in st.reason and "layer name" in st.reason


def test_probe_findings_pass_through():
    st = evaluate(spec(), ProbeResult(published=ago(0), findings=[Finding("warn", "a newer release is published")]), TODAY)
    assert st.state == "warn" and "newer release" in st.reason


# --- probe failures --------------------------------------------------------------------------

def test_one_transient_failure_warns_two_in_a_row_alarm():
    failed = ProbeResult(error=ProbeError("transient", "ConnectError"))
    assert evaluate(spec(), failed, TODAY).state == "warn"
    assert evaluate(spec(), failed, TODAY, previous_error=True).state == "alarm"


def test_a_service_error_body_is_an_error_at_once():
    st = evaluate(spec(), ProbeResult(error=ProbeError("service", "layer: 400 Failed to execute query")), TODAY)
    assert st.state == "error"


def test_a_probe_that_could_not_run_here_is_unknown_not_ok():
    st = evaluate(spec(), ProbeResult(skipped="ptaxsim.db not present here"), TODAY)
    assert st.state == "unknown" and "not present" in st.reason


# --- acks --------------------------------------------------------------------------------------

STALE = ProbeResult(published=ago(100))


def test_an_active_ack_turns_a_bad_state_into_acked():
    s = spec(ack=Ack("The publisher stopped updating; a fallback covers it.", date(2027, 1, 31), "jack"))
    st = evaluate(s, STALE, TODAY)
    assert st.state == "acked" and "alarm" in st.reason and "fallback" in st.reason


def test_an_expired_ack_becomes_an_alarm():
    s = spec(ack=Ack("The publisher stopped updating; a fallback covers it.", date(2026, 10, 20), "jack"))
    st = evaluate(s, STALE, TODAY)
    assert st.state == "alarm" and "ack expired 2026-10-20" in st.reason


def test_an_ack_on_a_recovered_source_changes_nothing():
    s = spec(ack=Ack("The publisher stopped updating; a fallback covers it.", date(2026, 10, 20), "jack"))
    assert evaluate(s, ProbeResult(published=ago(0)), TODAY).state == "ok"


def test_an_active_ack_also_covers_a_repeated_probe_failure():
    s = spec(ack=Ack("Known flaky host; revisit in January.", date(2027, 1, 31), "jack"))
    assert evaluate(s, ProbeResult(error=ProbeError("transient", "timeout")), TODAY, previous_error=True).state == "acked"


# --- a source with a working fallback can only warn -------------------------------------------

def test_a_source_with_a_working_fallback_only_warns():
    s = spec(warns_only_while_ok="cook.parcel_universe", warn_days=None, alarm_days=None, availability_only=True)
    failed = ProbeResult(error=ProbeError("transient", "timeout"))
    capped = evaluate(s, failed, TODAY, previous_error=True, peers={"cook.parcel_universe": "ok"})
    assert capped.state == "warn" and "capped at warn" in capped.reason
    both = evaluate(s, failed, TODAY, previous_error=True, peers={"cook.parcel_universe": "alarm"})
    assert both.state == "alarm"


# --- the run: probes, evaluation, and the fallback pass together ---------------------------------

def test_run_all_over_mocked_services_counts_requests_and_applies_the_fallback_cap():
    import json
    from pathlib import Path

    import httpx

    fix = Path(__file__).parent / "fixtures" / "data_health"
    view = json.loads((fix / "socrata_view_crime.json").read_text())
    from backend.data_health.registry import BY_ID

    def handle(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "cookVwrDynmc" in url:
            raise httpx.ConnectError("down", request=req)
        if "/api/views/" in url:
            return httpx.Response(200, json=view)
        return httpx.Response(404, json={"error": True, "message": "unrouted"})

    specs = (BY_ID["chi.divvy"], BY_ID["cook.parcel_universe"], BY_ID["cook.gis.parcels"])
    rows, requests = asyncio.run(check.run_all(specs, today=date(2026, 10, 21), transport=httpx.MockTransport(handle)))
    by = {r.spec.id: r.status for r in rows}
    assert by["chi.divvy"].state == "ok"
    assert by["cook.parcel_universe"].state == "ok"
    assert by["cook.gis.parcels"].state == "warn"  # down, but Parcel Universe works
    assert requests == 3
    out = check.render(rows, requests, 1.0)
    assert "cook.gis.parcels" in out and "3 HTTP requests" in out


def test_cli_requires_dry_run_and_rejects_an_unknown_source(capsys):
    with pytest.raises(SystemExit):
        check.main([])
    with pytest.raises(SystemExit):
        check.main(["--dry-run", "--only", "no.such.source"])
