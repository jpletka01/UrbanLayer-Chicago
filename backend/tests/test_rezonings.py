"""WS1 M5: rezonings Council passed that the City's map doesn't show yet.

Offline: the Clerk list is the recorded fixture, Address Points and the MapServer are faked.
The product statement under test is narrow: "a rezoning listing this address passed on <date>";
never that the parcel was rezoned, never to what.
"""

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.legislation import currency, rezonings, sync
from backend.legislation.address_titles import PARSER_VERSION
from backend.models import ContextObject, ZoningSummary
from backend.retrieval import clerk
from backend.retrieval.coverage_notes import build_coverage_notes
from backend.retrieval.property import address_points

FIXTURE = Path(__file__).parent / "fixtures" / "clerk" / "rezonings_2025-10-21.json"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 21)


def _run(coro):
    return asyncio.run(coro)


def _matter(record="SO2026-0028350", passed="2026-10-14", title=None, sub="Passed as Substitute") -> clerk.ClerkMatter:
    return clerk.ClerkMatter.from_api({
        "matterId": "mid-" + record, "recordNumber": record, "status": "90-Final", "subStatus": sub,
        "matterCategory": "ZONING RECLASSIFICATIONS", "type": "Ordinance",
        "title": title or "Zoning Reclassification Map No. 18-K at 6701-6717 S Western Ave - App No. A-9140",
        "finalActionDate": f"{passed}T15:00:00Z", "recordCreateDate": f"{passed}T15:00:00Z",
        "lastPublicationDate": f"{passed}T15:00:00Z", "introductionDate": "2026-09-01T15:00:00Z",
    })


def _pins(*pins):
    return [{"pin": p, "lat": 41.77, "lon": -87.68, "number": 6701, "name": "WESTERN"} for p in pins]


@pytest.fixture
def fake_world(monkeypatch):
    """Address Points returns two parcels for any segment; the map carries nothing unless told."""
    state = {"on_map": set(), "calls": []}

    async def records_on_map(records, *, client=None):
        state["calls"].append(list(records))
        return {r for r in records if r in state["on_map"]}

    async def pins_in_range(**kw):
        state.setdefault("ranges", []).append(kw)
        return _pins("17000000000001", "17000000000002") if kw["names"][0] == "WESTERN" else []

    monkeypatch.setattr(rezonings, "records_on_map", records_on_map)
    monkeypatch.setattr(address_points, "pins_in_range", pins_in_range)
    return state


# --- the daily build ----------------------------------------------------------------------------

def test_an_off_map_ordinance_is_parsed_and_its_parcels_resolved(fake_world):
    rows = _run(rezonings.build_rows([_matter()], overrides={}))
    r = rows[0]
    assert r["map_status"] == "off_map" and r["parse"]["status"] == "clean" and r["parser"] == PARSER_VERSION
    assert [p[0] for p in r["pins"]] == ["17000000000001", "17000000000002"]
    assert r["record"] == "SO2026-0028350" and r["substitute"] is True and r["passed_on"] == "2026-10-14"
    # the range, the street's spellings and the type forms reached Address Points
    q = fake_world["ranges"][0]
    assert (q["direction"], q["lo"], q["hi"], q["side"]) == ("S", 6701, 6717, "odd")
    assert q["names"] == ["WESTERN"] and q["types"] == ["AVE", "AVENUE"]


def test_an_on_map_ordinance_is_not_resolved_unless_asked(fake_world):
    fake_world["on_map"] = {"SO2026-0028350"}
    on = _run(rezonings.build_rows([_matter()], overrides={}))[0]
    assert on["map_status"] == "on_map" and on["pins"] is None and "ranges" not in fake_world
    bt = _run(rezonings.build_rows([_matter()], overrides={}, resolve_on_map=True))[0]
    assert bt["pins"] and "ranges" in fake_world


def test_a_partial_title_is_never_resolved_and_never_flagged(fake_world):
    m = _matter(record="O2026-0025379", title="Zoning Reclassification Map No. 4-J at 3600-3732 and 36333701 W 16th St - App No. A-9108")
    r = _run(rezonings.build_rows([m], overrides={}))[0]
    assert r["parse"]["status"] == "partial" and r["pins"] is None and "ranges" not in fake_world
    assert not rezonings.is_flaggable(r, TODAY)


def test_a_reviewed_override_stands_in_for_an_unreadable_title(fake_world):
    m = _matter(record="O2026-0025379", title="Zoning Reclassification Map No. 4-J at 3600-3732 and 36333701 W 16th St - App No. A-9108")
    seg = {"dir": "S", "name": "WESTERN", "type": "AVE", "lo": 3600, "hi": 3732, "side": "even", "raw": "3600-3732"}
    r = _run(rezonings.build_rows([m], overrides={"O2026-0025379": {"segments": [seg]}}))[0]
    assert r["source"] == "override" and r["parse"]["status"] == "clean" and r["pins"]


def test_parsing_and_parcels_are_reused_but_the_map_is_asked_again(fake_world):
    first = _run(rezonings.build_rows([_matter()], overrides={}))
    n = len(fake_world["ranges"])
    fake_world["on_map"] = {"SO2026-0028350"}   # the map caught up overnight
    second = _run(rezonings.build_rows([_matter()], first, overrides={}))
    assert len(fake_world["ranges"]) == n               # no new Address Points query
    assert second[0]["map_status"] == "on_map" and second[0]["pins"] == first[0]["pins"]


def test_a_parser_version_change_recomputes_everything(fake_world):
    first = _run(rezonings.build_rows([_matter()], overrides={}))
    first[0]["parser"] = PARSER_VERSION - 1
    n = len(fake_world["ranges"])
    _run(rezonings.build_rows([_matter()], first, overrides={}))
    assert len(fake_world["ranges"]) == n + 1


def test_segments_that_match_no_address_point_are_listed(fake_world):
    m = _matter(title="Zoning Reclassification Map No. 1-A at 10 N Nowhere Ave and 6701 S Western Ave - App No. 1")
    r = _run(rezonings.build_rows([m], overrides={}))[0]
    assert r["pins"] and r["unresolved"] == ["10 N NOWHERE AVE"]


def test_an_unreachable_map_is_an_error_not_everything_off_the_map(monkeypatch):
    class Down:
        async def post(self, *a, **k):
            raise ConnectionError("down")

    with pytest.raises(rezonings.MapCheckUnavailable):
        _run(rezonings.records_on_map(["O2026-1"], client=Down()))


def test_records_on_map_reads_clerk_docno_in_batches():
    seen = []

    class Resp:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body

    class Map:
        async def post(self, url, data=None, timeout=None):
            seen.append(data["where"])
            ids = [x.strip("'") for x in data["where"].split("(")[1].rstrip(")").split(",")]
            return Resp({"features": [{"attributes": {"CLERK_DOCNO": i}} for i in ids if i.endswith("0")]})

    records = [f"O2026-{i:07d}" for i in range(95)]
    found = _run(rezonings.records_on_map(records, client=Map()))
    assert len(seen) == 3 and "CLERK_DOCNO IN (" in seen[0]          # 40 + 40 + 15
    assert found == {r for r in records if r.endswith("0")}
    with pytest.raises(rezonings.MapCheckUnavailable):
        class Err(Map):
            async def post(self, *a, **k): return Resp({"error": {"message": "x"}})
        _run(rezonings.records_on_map(["O2026-1"], client=Err()))


# --- the request path --------------------------------------------------------------------------

def _row(**over):
    seg = {"dir": "S", "name": "WESTERN", "type": "AVE", "lo": 6701, "hi": 6717, "side": "odd", "raw": "6701-6717"}
    row = {
        "record": "SO2026-0028350", "passed_on": "2026-10-14", "url": "https://clerk/x", "map_status": "off_map",
        "parse": {"status": "clean", "segments": [seg], "notes": [], "maps": "18-K"}, "parser": PARSER_VERSION,
        "pins": [["17000000000001", 41.77, -87.68]], "unresolved": [],
    }
    row.update(over)
    return row


def _snap(*rows, status="ok", checked="2026-10-21T10:00:00Z"):
    return {"status": status, "checked_at": checked, "vintage": "2026-06-17", "rezonings": list(rows)}


def _match(snap, pin="17000000000001", address="6711 S Western Ave", live=None):
    return rezonings.matches_for(pin, address, live, snapshot=snap, today=TODAY)


def test_a_parcel_in_an_off_map_ordinance_is_flagged_by_pin(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    hits = _match(_snap(_row()))
    assert len(hits) == 1
    h = hits[0]
    assert (h["record"], h["passed_on"], h["matched_by"], h["url"]) == ("SO2026-0028350", "2026-10-14", "pin", "https://clerk/x")
    assert h["segment"] == "6701-6717 S Western Ave" and h["maps"] == "18-K"


def test_a_parcel_the_map_already_credits_to_that_ordinance_is_not_flagged(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    assert _match(_snap(_row()), live="SO2026-0028350") == []


def test_an_ordinance_on_the_map_flags_nothing(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    assert _match(_snap(_row(map_status="on_map"))) == []


def test_a_parcel_outside_the_pin_set_is_not_flagged(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    assert _match(_snap(_row()), pin="17000000009999") == []


def test_unresolved_pin_matches_on_the_parsed_address(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    snap = _snap(_row())
    assert _match(snap, pin=None, address="6711 S Western Ave")[0]["matched_by"] == "address"
    assert _match(snap, pin=None, address="6712 S Western Ave") == []      # the even side of the street
    assert _match(snap, pin=None, address="6719 S Western Ave") == []      # past the range
    assert _match(snap, pin=None, address="6711 N Western Ave") == []      # wrong direction
    assert _match(snap, pin=None, address="6711 S Western Pl") == []       # a different street type
    assert _match(snap, pin=None, address="6711 S Damen Ave") == []        # a different street
    assert _match(snap, pin=None, address=None) == []


def test_a_stale_failed_or_suspect_snapshot_flags_nothing(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    assert _match(_snap(_row(), checked="2026-09-01T10:00:00Z")) == []      # over 14 days old: it might have reached the map
    assert _match(_snap(_row(), status="failed")) == []
    assert _match(_snap(_row(), status="suspect")) == []
    assert _match(None) == []


def test_only_the_last_year_is_flagged_and_newest_comes_first(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    old = _row(record="O2025-0000001", passed_on="2025-10-01")
    newer = _row(record="O2026-0000002", passed_on="2026-10-01")
    assert [h["record"] for h in _match(_snap(old, newer))] == ["O2026-0000002"]
    both = _row(record="O2026-0000003", passed_on="2026-06-01")
    assert [h["record"] for h in _match(_snap(both, newer))] == ["O2026-0000002", "O2026-0000003"]


def test_the_overrides_file_is_optional_and_never_fatal(tmp_path):
    assert rezonings.load_overrides(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert rezonings.load_overrides(bad) == {}
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"overrides": {"O1": {"segments": []}, "O2": "junk"}}))
    assert set(rezonings.load_overrides(ok)) == {"O1"}
    assert rezonings.load_overrides() == {}   # the committed file starts empty


def test_summary_counts_for_the_log_and_admin(fake_world):
    rows = [_row(), _row(record="O2", parse={"status": "partial", "segments": [], "notes": ["x"]}, pins=None),
            _row(record="O3", map_status="on_map"), _row(record="O4", pins=[])]
    s = rezonings.summary(rows)
    assert (s["passed"], s["off_map"], s["flaggable"]) == (4, 3, 2)
    assert s["unparsed"] == ["O2"] and s["no_parcels"] == ["O4"]


# --- the sync ---------------------------------------------------------------------------------

def test_sync_stores_rezonings_and_counts(monkeypatch, fake_world, tmp_path):
    from backend.tests.test_legislation_currency import _matters

    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=_matters()))
    monkeypatch.setattr(clerk, "passed_since", AsyncMock(return_value=[_matter()]))
    code, snap = _run(sync.run(tmp_path / "s.json"))
    assert code == 0
    assert [r["record"] for r in snap["rezonings"]] == ["SO2026-0028350"]
    rc = snap["rezoning_check"]
    assert rc["status"] == "ok" and rc["counts"]["off_map"] == 1 and rc["counts"]["flaggable"] == 1


def test_a_rezoning_failure_keeps_the_previous_rows_and_the_code_amendment_check(monkeypatch, fake_world, tmp_path):
    from backend.tests.test_legislation_currency import _matters

    monkeypatch.setattr(clerk, "final_since", AsyncMock(return_value=_matters()))
    monkeypatch.setattr(clerk, "passed_since", AsyncMock(return_value=[_matter()]))
    out = tmp_path / "s.json"
    _, first = _run(sync.run(out))
    monkeypatch.setattr(rezonings, "records_on_map", AsyncMock(side_effect=rezonings.MapCheckUnavailable("503")))
    code, second = _run(sync.run(out))
    assert code == 0 and second["status"] == "ok"                         # code amendments still checked
    assert second["rezonings"] == first["rezonings"]                       # last good rows kept
    assert second["rezoning_check"]["status"] == "failed" and "503" in second["rezoning_check"]["last_error"]
    assert second["rezoning_check"]["checked_at"] == first["rezoning_check"]["checked_at"]


# --- where it shows ---------------------------------------------------------------------------

def test_the_coverage_note_says_a_listing_not_a_rezoning():
    hit = {"record": "SO2026-0028350", "passed_on": "2026-10-14", "url": "https://clerk/x", "segment": "6701-6717 S Western Ave"}
    notes = build_coverage_notes(
        zoning=ZoningSummary(zone_class="B3-2"), regulatory=None, property_=None, neighborhood=None, adu=None,
        code_vintage=None, passed_not_on_map=[hit],
    )
    n = next(n for n in notes if n["id"] == "passed_not_on_map")
    assert n["applies"] == "parcel" and n["link"] == "https://clerk/x"
    assert n["params"] == {"date": "2026-10-14", "record": "SO2026-0028350", "segment": "6701-6717 S Western Ave"}
    assert "listing this address passed City Council on Oct 14, 2026 (SO2026-0028350)" in n["text"]
    assert "has not been updated" in n["text"] and "still shows" in n["text"]
    assert "was rezoned" not in n["text"] and "rezoned to" not in n["text"]
    assert not any(n["id"] == "passed_not_on_map" for n in build_coverage_notes(
        zoning=ZoningSummary(zone_class="B3-2"), regulatory=None, property_=None, neighborhood=None, adu=None, code_vintage=None))


def test_the_context_object_derives_the_field_and_the_note(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    snap = _snap(_row())
    monkeypatch.setattr(currency, "load_snapshot", lambda: snap)
    ctx = ContextObject(resolved_address="6711 S Western Ave", parcel_pin="17000000000001",
                        parcel_resolution="authoritative", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    assert ctx.passed_not_on_map and ctx.passed_not_on_map[0]["record"] == "SO2026-0028350"
    assert any(n["id"] == "passed_not_on_map" for n in ctx.coverage_notes)
    assert "passed_not_on_map" in ctx.model_dump()                          # rides the chat context and the Profile JSON
    # the parcel the map already credits to that ordinance: nothing
    again = ctx.model_copy(update={"parcel_zoning": ZoningSummary(zone_class="B3-2", ordinance_num="SO2026-0028350")})
    assert again.passed_not_on_map is None
    # an approximate parcel's PIN is withheld, so the address decides
    approx = ctx.model_copy(update={"parcel_resolution": "approximate", "parcel_pin": "17000000009999"})
    assert approx.passed_not_on_map[0]["matched_by"] == "address"
    assert ContextObject().passed_not_on_map is None


# --- Address Points range query --------------------------------------------------------------------

def test_pins_in_range_filters_parity_and_malformed_pins(monkeypatch):
    rows = [
        {"pin": "17000000000001", "lat": "41.7", "long": "-87.6", "add_number": "6701", "st_name": "WESTERN"},
        {"pin": "17000000000002", "lat": "41.7", "long": "-87.6", "add_number": "6702", "st_name": "WESTERN"},   # even side
        {"pin": "170000000003", "lat": "41.7", "long": "-87.6", "add_number": "6703", "st_name": "WESTERN"},     # malformed
        {"pin": "00000000000000", "lat": "41.7", "long": "-87.6", "add_number": "6705", "st_name": "WESTERN"},
        {"pin": "17000000000001", "lat": "41.7", "long": "-87.6", "add_number": "6709", "st_name": "WESTERN"},   # same parcel, 2nd point
        {"pin": "17000000000004", "lat": "41.7", "long": "-87.6", "add_number": "x", "st_name": "WESTERN"},      # junk number
    ]
    seen = {}

    async def fake(dataset, params, **kw):
        seen["where"] = params["$where"]
        return rows

    monkeypatch.setattr(address_points, "socrata_get", fake)
    out = _run(address_points.pins_in_range(direction="S", names=["WESTERN"], types=["AVE", "AVENUE"], lo=6701, hi=6717, side="odd"))
    assert [(r["pin"], r["number"]) for r in out] == [("17000000000001", 6701)]
    w = seen["where"]
    assert "inc_muni='Chicago'" in w and "in ('S','SOUTH')" in w and "in ('WESTERN')" in w
    assert "in ('AVE','AVENUE')" in w and "between 6701 and 6717" in w
    both = _run(address_points.pins_in_range(direction="S", names=["WESTERN"], types=["AVE"], lo=6701, hi=6717, side="both"))
    assert [r["pin"] for r in both] == ["17000000000001", "17000000000002"]


# --- chat and the report ----------------------------------------------------------------------

def _ctx_with_hit(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)
    snap = _snap(_row())
    monkeypatch.setattr(currency, "load_snapshot", lambda: snap)
    return ContextObject(resolved_address="6711 S Western Ave", parcel_pin="17000000000001",
                         parcel_resolution="authoritative", parcel_zoning=ZoningSummary(zone_class="B3-2"))


def test_prompt_rule_says_listing_never_rezoned_and_never_the_new_district():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("34. HOW CURRENT THE ZONING IS")
    rule = SYNTHESIZER_SYSTEM[i: SYNTHESIZER_SYSTEM.index("35. OVERLAYS")]
    assert "`passed_not_on_map`" in rule and "listing this address" in rule
    assert "Never say the parcel was rezoned" in rule and "never state new standards" in rule
    assert "A missing list is not proof" in rule


def test_the_model_sees_the_listing_and_may_link_it(monkeypatch):
    from backend.chat_sources import allowed_urls, _norm

    ctx = _ctx_with_hit(monkeypatch)
    payload = json.loads(ctx.model_dump_json(exclude={"analytics"}))
    assert payload["passed_not_on_map"][0]["record"] == "SO2026-0028350"
    assert any(n["id"] == "passed_not_on_map" for n in payload["coverage_notes"])
    assert _norm("https://clerk/x") in allowed_urls(ctx)


def _report_html(ctx, language="en"):
    from backend.main import render_report_html
    from backend.models import ReportData

    return render_report_html(ReportData(address="6711 S Western Ave", language=language, context=ctx), language,
                              report_date="October 21, 2026")


def test_the_report_warns_prominently_that_the_map_district_may_be_old(monkeypatch):
    html = _report_html(_ctx_with_hit(monkeypatch))
    assert "A rezoning passed that the City&#39;s map does not show yet" in html
    assert "listing this address (6701-6717 S Western Ave) passed City Council on October 14, 2026 (SO2026-0028350)" in html
    assert 'href="https://clerk/x"' in html
    assert "was rezoned" not in html
    es = _report_html(_ctx_with_hit(monkeypatch), "es")
    assert "14 de octubre de 2026" in es and "(SO2026-0028350)" in es    # the English text until WS7, with the date localized


def test_the_report_is_silent_without_a_listing(monkeypatch):
    monkeypatch.setattr(currency, "load_snapshot", lambda: None)
    ctx = ContextObject(resolved_address="6711 S Western Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    assert "does not show yet" not in _report_html(ctx)


def test_map_lag_status_for_the_admin_and_the_registry(monkeypatch):
    monkeypatch.setattr(currency, "load_snapshot", lambda: None)
    assert currency.map_lag_status()["check_status"] == "missing"
    assert currency.map_lag_status()["passed_not_on_map"] is None      # never "0" when nothing was checked
    rows = [_row(passed_on="2026-07-15"), _row(record="O2", parse={"status": "partial", "segments": [], "notes": ["x"]}, pins=None),
            _row(record="O3", map_status="on_map")]
    snap = {**_snap(*rows), "rezoning_check": {"status": "ok", "checked_at": "2026-10-21T10:00:00Z"}}
    monkeypatch.setattr(currency, "load_snapshot", lambda: snap)
    s = currency.map_lag_status()
    assert (s["passed_not_on_map"], s["unparsed_titles"], s["unparsed"]) == (2, 1, ["O2"])
    assert s["source_id"] == "chi.zoning.passed_not_on_map" and s["check_status"] == "ok" and s["oldest_days"] >= 98
    assert s["district_read_agreement"] is None
