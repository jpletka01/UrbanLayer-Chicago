"""Probe parsers on recorded responses, and the probes over a mock transport (no network)."""

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from backend.data_health import probes
from backend.data_health.evaluate import ProbeError
from backend.data_health.registry import BY_ID, SOURCES

FIX = Path(__file__).parent / "fixtures" / "data_health"


def fx(name: str):
    return json.loads((FIX / name).read_text())


# --- parsers on recorded fixtures --------------------------------------------------------------

def test_socrata_view_gives_publisher_date_and_columns():
    published, fields = probes.parse_socrata_view(fx("socrata_view_crime.json"))
    assert published == date(2026, 10, 21)
    assert {"date", "year", "updated_on"} <= set(fields)


def test_socrata_error_bodies_are_errors_not_empty_results():
    with pytest.raises(ProbeError) as e:
        probes.parse_socrata_view(fx("socrata_view_notfound.json"), "zzzz view")
    assert e.value.kind == "service" and "Not found" in e.value.text
    with pytest.raises(ProbeError) as e:
        probes.parse_socrata_max(fx("socrata_error_bad_column.json"), "max_date")
    assert e.value.kind == "service" and "no-such-column" in e.value.text


def test_socrata_max_date_and_year():
    assert probes.parse_socrata_max(fx("socrata_max_date.json"), "max_date") == date(2026, 10, 13)
    # A year is judged as the last day of that year: 2026 is not 'stale' on January 2.
    assert probes.parse_socrata_max(fx("socrata_max_year.json"), "max_year") == date(2026, 12, 31)
    assert probes.parse_socrata_max([], "max_date") is None
    assert probes.parse_socrata_max([{"m": None}], "max_date") is None


def test_arcgis_layer_name_fields_and_edit_date():
    info = probes.parse_arcgis_layer(fx("arcgis_layer1.json"))
    assert info.name == "Zoning Boundaries"
    assert {"ZONE_CLASS", "UPDATE_TIMESTAMP", "CLERK_URL"} <= set(info.fields)
    assert info.edited is None  # this server reports no editingInfo
    epa = probes.parse_arcgis_layer(fx("arcgis_layer_editinginfo.json"))
    assert epa.edited is not None and epa.edited.year >= 2026


def test_arcgis_200_with_error_body_is_an_error():
    for name in ("arcgis_error_200.json", "arcgis_error_bad_layer.json"):
        with pytest.raises(ProbeError) as e:
            probes.parse_arcgis_layer(fx(name))
        assert e.value.kind == "service"
    with pytest.raises(ProbeError):
        probes.parse_arcgis_count(fx("arcgis_error_200.json"))
    with pytest.raises(ProbeError):
        probes.parse_arcgis_newest(fx("arcgis_error_200.json"), "UPDATE_TIMESTAMP")


def test_arcgis_count_and_newest_edit():
    assert probes.parse_arcgis_count(fx("arcgis_count.json")) > 14_000
    assert probes.parse_arcgis_newest(fx("arcgis_newest.json"), "UPDATE_TIMESTAMP").year == 2026
    assert probes.parse_arcgis_newest({"features": []}, "UPDATE_TIMESTAMP") is None


def test_arcgis_outstatistics_is_not_used():
    """`outStatistics max()` returns a wrong value on this server (verified 2026-10-20): the
    newest-edit query orders and takes one row instead."""
    params = probes.arcgis_newest_params("UPDATE_TIMESTAMP")
    assert "outStatistics" not in params and "outStatistics" not in json.dumps(params)
    assert params["orderByFields"] == "UPDATE_TIMESTAMP DESC" and params["resultRecordCount"] == "1"
    assert "outStatistics" not in probes.arcgis_count_params()


def test_census_release_end_year():
    rel_id, years, end = probes.parse_census_release(fx("census_release.json"))
    assert (rel_id, years, end) == ("acs2024_5yr", "2020-2024", 2024)
    with pytest.raises(ProbeError):
        probes.parse_census_release({"release": {}})


def test_last_modified_header():
    assert probes.parse_last_modified(fx("headers_cta_gtfs.json")) == date(2026, 9, 14)
    assert probes.parse_last_modified({}) is None


def test_ptaxsim_metadata_and_next_release():
    version, created, last_year = probes.parse_ptaxsim_metadata(fx("ptaxsim_metadata.json"))
    assert (version, created, last_year) == ("2024.0.0", date(2026, 5, 6), 2024)
    assert probes.next_ptaxsim_version(version) == "2025.0.0"
    assert probes.next_ptaxsim_version("garbage") is None


def test_geocoder_known_answer_is_within_tolerance():
    pt = probes.parse_geocoder_point(fx("geocoder_lasalle.json"))
    assert pt is not None
    assert probes.meters_between(*pt, *probes.GEOCODER_EXPECTED) < probes.GEOCODER_TOLERANCE_M
    assert probes.parse_geocoder_point({"result": {"addressMatches": []}}) is None


def test_error_text_never_carries_a_query_string():
    """Walk Score's key travels in the query string; an httpx error message quotes the URL."""
    msg = "ConnectError: https://api.walkscore.com/score?format=json&wsapikey=SECRET123 failed"
    cleaned = probes._clean(msg)
    assert "SECRET123" not in cleaned and "wsapikey" not in cleaned


# --- registry wiring ---------------------------------------------------------------------------

def test_every_named_probe_exists():
    for s in SOURCES:
        if s.probe and s.probe != "none":
            assert s.probe in probes.PROBES, f"{s.id}: probe {s.probe!r} is not defined"


def test_sources_with_no_probe_are_the_planned_placeholders():
    none = {s.id for s in SOURCES if probes.probe_for(s) is None}
    frozen_artifacts = {s.id for s in SOURCES if s.kind == "artifact" and s.frozen}
    assert none - frozen_artifacts == {"artifact.transit_stations", "eval.kit_weekly"}


# --- probes over a mock transport ------------------------------------------------------------

def _handler(routes: dict[str, object], status: dict[str, int] | None = None):
    status = status or {}

    def handle(req: httpx.Request) -> httpx.Response:
        for needle, body in routes.items():
            if needle in str(req.url):
                code = next((c for n, c in status.items() if n in str(req.url)), 200)
                return httpx.Response(code, json=body)
        return httpx.Response(404, json={"error": True, "message": f"unrouted {req.url}"})

    return handle


def _run(spec, handler):
    async def go():
        client, total = probes.make_client(httpx.MockTransport(handler))
        ctx = probes.ProbeContext(client=client, sem=asyncio.Semaphore(4), today=date(2026, 10, 21))
        try:
            return await probes.run_probe(spec, ctx), total()
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_socrata_probe_reads_view_and_max_in_two_requests():
    spec = BY_ID["chi.crime"]
    res, n = _run(spec, _handler({
        "/api/views/ijzp-q8t2.json": fx("socrata_view_crime.json"),
        "/resource/ijzp-q8t2.json": fx("socrata_max_date.json"),
    }))
    assert n == 2 and res.requests == 2
    assert res.published == date(2026, 10, 21) and res.content == date(2026, 10, 13) and res.error is None


def test_socrata_probe_with_no_content_column_is_one_request():
    res, n = _run(BY_ID["chi.divvy"], _handler({"/api/views/bbyy-e7gq.json": fx("socrata_view_crime.json")}))
    assert n == 1 and res.content is None and res.published is not None


def test_arcgis_probe_reads_layer_count_and_newest_edit():
    spec = BY_ID["chi.zoning.districts"]

    def handle(req: httpx.Request) -> httpx.Response:
        if "returnDistinctValues" in str(req.url):  # the ZONE_CLASS value-set read (M4)
            return httpx.Response(200, json={"features": [{"attributes": {"ZONE_CLASS": "B3-2"}}, {"attributes": {"ZONE_CLASS": "PD 835"}}]})
        if "returnCountOnly" in str(req.url):
            return httpx.Response(200, json=fx("arcgis_count.json"))
        if "orderByFields" in str(req.url):
            return httpx.Response(200, json=fx("arcgis_newest.json"))
        return httpx.Response(200, json=fx("arcgis_layer1.json"))

    res, n = _run(spec, handle)
    assert n == 4 and res.layer_name == "Zoning Boundaries" and res.count > 14_000 and res.content.year == 2026
    assert res.values == {"ZONE_CLASS": ("B3-2", "PD 835")}


def test_a_200_with_an_error_body_is_a_service_error():
    res, _ = _run(BY_ID["chi.zoning.districts"], _handler({"/MapServer/1": fx("arcgis_error_200.json")}))
    assert res.error and res.error.kind == "service"


def test_a_5xx_is_a_transient_error():
    res, _ = _run(BY_ID["chi.crime"], _handler({"/api/views/": {"error": True}, "/resource/": []}, {"/api/views/": 503}))
    assert res.error and res.error.kind == "transient"


def test_a_connection_failure_is_transient_and_never_raises():
    def boom(req):
        raise httpx.ConnectError("connection refused", request=req)

    res, _ = _run(BY_ID["chi.crime"], boom)
    assert res.error and res.error.kind == "transient"


def test_acs_community_area_probe_reads_the_census_release_as_its_reference():
    spec = BY_ID["chi.acs_community_area"]
    res, n = _run(spec, _handler({
        "/api/views/t68z-cikk.json": fx("socrata_view_crime.json"),
        "/resource/t68z-cikk.json": [{"m": "2023"}],
        "api.censusreporter.org": fx("census_release.json"),
    }))
    assert res.content_year == 2023 and res.reference_year == 2024
    # the crime fixture has no 'acs_year' column, so the probe also flags the content column
    assert any("acs_year" in f.text for f in res.findings)
    assert n == 3


def test_the_census_release_is_read_once_for_all_dependants():
    async def go():
        client, total = probes.make_client(httpx.MockTransport(_handler({"api.censusreporter.org": fx("census_release.json")})))
        ctx = probes.ProbeContext(client=client, sem=asyncio.Semaphore(4), today=date(2026, 10, 21))
        try:
            await asyncio.gather(ctx.census_latest(), ctx.census_latest(), probes.probe_census_release(BY_ID["census.reporter.acs"], ctx))
            return total()
        finally:
            await client.aclose()

    assert asyncio.run(go()) == 1


def test_gtfs_probe_uses_head_and_reads_last_modified():
    seen = []

    def handle(req: httpx.Request) -> httpx.Response:
        seen.append(req.method)
        return httpx.Response(200, headers={"last-modified": fx("headers_cta_gtfs.json")["last-modified"]})

    res, n = _run(BY_ID["chi.cta.gtfs"], handle)
    assert seen == ["HEAD"] and n == 1 and res.published == date(2026, 9, 14)


def test_walkscore_without_a_key_is_skipped_not_green(monkeypatch):
    class NoKey:
        walkscore_api_key = ""
        socrata_app_token = ""
        cook_county_socrata_token = ""

    monkeypatch.setattr(probes, "get_settings", lambda: NoKey())
    res, n = _run(BY_ID["private.walkscore"], _handler({}))
    assert res.skipped and n == 0


def test_hand_table_and_code_text_probes_read_local_files_only():
    res, n = _run(BY_ID["code.hand_table.zoning_definitions"], _handler({}))
    assert n == 0 and res.error is None and not res.findings
    res, n = _run(BY_ID["code.municipal_text"], _handler({}))
    assert n == 0 and res.content == date.fromisoformat(json.loads((Path(__file__).parents[1] / "code_vintage.json").read_text())["current_through"])


# --- backup age and the checker's own run (WS6 M2) ---------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

_NOW = datetime(2026, 10, 21, 5, 37, tzinfo=timezone.utc)


def _status(hours_old: float, **kw):
    done = _NOW - timedelta(hours=hours_old)
    return {"completed_at": done.isoformat(), "newest_backup": "urbanlayer_x.db", "size_bytes": 4096, "retained": 7, **kw}


@pytest.mark.parametrize("hours,level", [(2.6, None), (30, None), (30.1, "warn"), (36, "warn"), (36.1, "alarm"), (200, "alarm")])
def test_backup_age_thresholds(hours, level):
    """The cron runs at 03:00 and the check at 05:37, so a healthy copy is ~2.6 h old; one missed night is ~26 h."""
    _, _, findings = probes.parse_backup_status(_status(hours), _NOW)
    assert (findings[0].level if findings else None) == level


def test_backup_status_reports_the_day_and_flags_an_empty_copy():
    day, info, findings = probes.parse_backup_status(_status(3, size_bytes=0), _NOW)
    assert day == date(2026, 10, 21) and "7 retained" in info
    assert [f.level for f in findings] == ["alarm"] and "empty" in findings[0].text


@pytest.mark.parametrize("body", [[], {}, {"completed_at": "yesterday-ish"}])
def test_backup_status_with_the_wrong_shape_is_a_service_error(body):
    with pytest.raises(ProbeError) as e:
        probes.parse_backup_status(body, _NOW)
    assert e.value.kind == "service"


def _probe(name, settings, tmp_path):
    spec = BY_ID[name]
    ctx = probes.ProbeContext(client=None, sem=asyncio.Semaphore(1), today=date(2026, 10, 21))
    return asyncio.run(probes.PROBES[spec.probe](spec, ctx))


def test_missing_backup_status_is_unknown_in_dev_and_an_alarm_where_backups_are_required(tmp_path, monkeypatch):
    from types import SimpleNamespace
    def mk(required):
        return SimpleNamespace(backup_status_path=tmp_path / "backup_status.json", backup_status_required=required)

    monkeypatch.setattr(probes, "get_settings", lambda: mk(False))
    assert _probe("internal.backups", None, tmp_path).skipped
    monkeypatch.setattr(probes, "get_settings", lambda: mk(True))
    res = _probe("internal.backups", None, tmp_path)
    assert res.skipped is None and res.findings[0].level == "alarm" and "missing" in res.findings[0].text


def test_a_stale_backup_status_file_alarms_through_evaluate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.data_health.evaluate import evaluate
    old = datetime.now(timezone.utc) - timedelta(hours=60)
    f = tmp_path / "backup_status.json"
    f.write_text(json.dumps({"completed_at": old.isoformat(), "newest_backup": "urbanlayer_x.db", "size_bytes": 9, "retained": 7}))
    monkeypatch.setattr(probes, "get_settings", lambda: SimpleNamespace(backup_status_path=f, backup_status_required=True))
    res = _probe("internal.backups", None, tmp_path)
    st = evaluate(BY_ID["internal.backups"], res, date.today())
    assert st.state == "alarm" and "h old" in st.reason
    f.write_text(json.dumps({"completed_at": datetime.now(timezone.utc).isoformat(), "size_bytes": 9, "retained": 7}))
    assert evaluate(BY_ID["internal.backups"], _probe("internal.backups", None, tmp_path), date.today()).state == "ok"


def test_checker_probe_reads_the_last_finished_run(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.data_health.evaluate import evaluate
    from backend.data_health.store import Store
    path = tmp_path / "h.db"
    monkeypatch.setattr(probes, "get_settings", lambda: SimpleNamespace(data_health_db_path=path))
    assert _probe("internal.checker", None, tmp_path).skipped                      # no store yet
    with Store(path) as s:
        rid = s.start_run(_NOW - timedelta(days=3))
        s.finish_run(rid, _NOW - timedelta(days=3), sources=1, alarms=0, requests=1)
    res = _probe("internal.checker", None, tmp_path)
    assert evaluate(BY_ID["internal.checker"], res, date(2026, 10, 21)).state == "warn"       # 3 days: past warn (1)
    assert evaluate(BY_ID["internal.checker"], res, date(2026, 10, 25)).state == "alarm"


def test_the_default_client_retries_connection_errors():
    """FEMA resets many fresh connections; a probe must not report that as the source being down."""
    client, _ = probes.make_client()
    try:
        assert client._transport._pool._retries == probes.CONNECT_RETRIES   # httpx has no public accessor
    finally:
        asyncio.run(client.aclose())
