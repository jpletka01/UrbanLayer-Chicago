"""WS1 M5b: Chicago Landmark designations Council has passed that the City's landmark map doesn't show on a parcel.

Offline: the Clerk titles are a recorded fixture (the 15 designations of the 400 days to 2026-10-22), Address Points
is faked. The product statement under test is narrow: "a designation ordinance *listing this address* passed on
<date>"; never that the parcel IS a landmark. The map is not compared by name: the parcel's own landmark-layer
result decides whether there is anything to add.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.legislation import currency, designation_titles as dt, designations, sync
from backend.models import ContextObject, RegulatorySummary, ZoningSummary
from backend.retrieval import clerk
from backend.retrieval.coverage_notes import build_coverage_notes, landmark_designation_text
from backend.retrieval.property import address_points

FIXTURE = Path(__file__).parent / "fixtures" / "clerk" / "landmark_designations_2026-10-22.json"
ROWS = json.loads(FIXTURE.read_text())["rows"]
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 22)


def _run(coro):
    return asyncio.run(coro)


def _matter(record="O2026-0027059", passed="2026-09-23", title=None) -> clerk.ClerkMatter:
    return clerk.ClerkMatter.from_api({
        "matterId": "mid-" + record, "recordNumber": record, "status": "90-Final", "subStatus": "Passed",
        "matterCategory": "HISTORICAL LANDMARKS | Designation", "type": "Ordinance",
        "title": title or "Historical landmark designation for Erie Street Row at 161 E Erie St",
        "finalActionDate": f"{passed}T15:00:00Z", "recordCreateDate": f"{passed}T15:00:00Z",
        "lastPublicationDate": f"{passed}T15:00:00Z", "introductionDate": "2026-09-01T15:00:00Z",
    })


# --- the titles the Clerk actually sent -------------------------------------------------------------------------

# record -> (kind, [(dir, name, type, lo, hi, side)]) as read by hand from the title
EXPECTED = {
    "O2025-0019121": ("building", [("E", "ERIE", "ST", 161, 161, "both")]),
    "O2025-0019626": ("building", [("N", "LARAMIE", "AVE", 1400, 1400, "both")]),
    "O2025-0020463": ("building", [("W", "ADAMS", "ST", 105, 105, "both")]),
    "O2025-0020890": ("building", [("S", "LASALLE", "ST", 19, 19, "both")]),
    "O2025-0021479": ("district", [("N", "HUMBOLDT", "BLVD", 1600, 1899, "both"), ("N", "SACRAMENTO", "AVE", 1000, 1199, "both"),
                                   ("N", "SACRAMENTO", "BLVD", 900, 999, "even")]),
    "O2026-0022515": ("building", [("N", "PINE", "AVE", 515, 515, "both")]),
    "O2026-0023266": ("building", [("N", "LASALLE", "ST", 30, 30, "both")]),
    "O2026-0023890": ("building", [("S", "DEARBORN", "ST", 4644, 4644, "both")]),
    "O2026-0024658": ("building", [("N", "HALSTED", "ST", 1926, 1926, "both")]),
    "O2026-0024659": ("building", [("N", "KENMORE", "AVE", 2219, 2219, "both")]),
    "O2026-0024660": ("building", [("N", "CHALMERS", "ST", 2324, 2324, "both")]),
    "O2026-0026117": ("building", [("N", "RIVERSIDE", "PLZ", 2, 2, "both"), ("W", "MONROE", "ST", 400, 400, "both")]),
    "O2026-0027058": ("building", [("S", "ELLIS", "AVE", 13100, 13100, "both")]),
    "O2026-0027059": ("district", [("W", "BRYN MAWR", "AVE", 900, 1199, "both")]),
}
UNREAD = {"O2025-0019665"}  # "5830 W Midway Park": a street with no type we recognize


def test_the_fixture_is_every_designation_and_the_table_covers_them():
    assert len(ROWS) == 15 and {r["record"] for r in ROWS} == set(EXPECTED) | UNREAD


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["record"])
def test_each_real_title_reads_as_a_person_reads_it(row):
    p = dt.parse_title(row["title"])
    if row["record"] in UNREAD:
        assert p.status == "unparsed" and p.segments == [] and any("Midway Park" in n for n in p.notes)
        return
    kind, segs = EXPECTED[row["record"]]
    assert p.status == "clean" and p.notes == [] and p.kind == kind
    assert [(s.dir, s.name, s.type, s.lo, s.hi, s.side) for s in p.segments] == segs


def test_a_name_that_contains_at_is_not_split_there():
    p = dt.parse_title("Historical landmark designation for Shop Building at Altgeld Gardens located at 13100 S Ellis Ave")
    assert p.name == "Shop Building at Altgeld Gardens" and p.segments[0].lo == 13100


def test_a_block_is_a_hundred_and_a_side_is_a_parity():
    p = dt.parse_title("Historical landmark designation for Row District at 200-300 blocks of W Fullerton Pkwy and North Side of 400 block of W Belden Ave")
    assert [(s.name, s.lo, s.hi, s.side) for s in p.segments] == [("FULLERTON", 200, 399, "both"), ("BELDEN", 400, 499, "even")]
    s = dt.parse_title("Historical landmark designation for Row District at West Side of 900 block of N Sacramento Blvd").segments[0]
    assert (s.lo, s.hi, s.side) == (900, 999, "odd")  # west side of a north-south street: odd


def test_a_side_on_the_wrong_axis_or_an_unknown_street_is_never_guessed():
    p = dt.parse_title("Historical landmark designation for Row District at East Side of 900 block of W Bryn Mawr Ave")
    assert p.status == "unparsed" and p.segments == [] and any("east side" in n for n in p.notes)
    p = dt.parse_title("Historical landmark designation for Mixed Row at 161 E Erie St and 5830 W Midway Park")
    assert p.status == "partial" and len(p.segments) == 1  # the unreadable half is noted, the readable half kept for review
    for bad in ("Zoning Reclassification Map No. 1-A at 10 N Nowhere Ave", "", "Historical landmark designation for Foo"):
        assert dt.parse_title(bad).status == "unparsed"


def test_a_fused_or_reversed_or_wide_listing_is_not_read():
    assert dt.parse_title("Historical landmark designation for X at 12345678901 N Foo Ave").status == "unparsed"
    assert dt.parse_title("Historical landmark designation for X at 1800-1600 blocks of N Foo Ave").status == "unparsed"
    assert dt.parse_title("Historical landmark designation for X at 100-9000 blocks of N Foo Ave").status == "unparsed"


# --- the daily build ----------------------------------------------------------------------------------------------

@pytest.fixture
def fake_world(monkeypatch):
    state = {"ranges": []}

    async def pins_in_range(**kw):
        state["ranges"].append(kw)
        if kw["names"][0] in ("ERIE", "BRYN MAWR"):
            return [{"pin": "17000000000001", "lat": 41.89, "lon": -87.62, "number": kw["lo"], "name": kw["names"][0]},
                    {"pin": "17000000000002", "lat": 41.89, "lon": -87.62, "number": kw["lo"] + 2, "name": kw["names"][0]}]
        return []

    monkeypatch.setattr(address_points, "pins_in_range", pins_in_range)
    return state


def test_a_clean_title_has_its_parcels_resolved_and_a_partial_one_does_not(fake_world):
    rows = _run(designations.build_rows([_matter(), _matter(record="O2025-0019665", title=ROWS[2]["title"])]))
    clean = next(r for r in rows if r["record"] == "O2026-0027059")
    assert clean["parse"]["status"] == "clean" and [p[0] for p in clean["pins"]] == ["17000000000001", "17000000000002"]
    assert clean["parse"]["name"] == "Erie Street Row" and clean["parse"]["kind"] == "building"
    q = fake_world["ranges"][0]
    assert (q["direction"], q["lo"], q["hi"], q["side"]) == ("E", 161, 161, "both") and q["types"] == ["ST", "STREET"]
    unread = next(r for r in rows if r["record"] == "O2025-0019665")
    assert unread["parse"]["status"] == "unparsed" and unread["pins"] == [] and len(fake_world["ranges"]) == 1


def test_segments_that_match_no_address_point_are_listed(fake_world):
    r = _run(designations.build_rows([_matter(title="Historical landmark designation for Chicago Daily News Building at 2 N Erie St/400 W Monroe St")]))[0]
    assert r["pins"] and r["unresolved"] == ["400 W MONROE ST"]


def test_parcels_are_reused_and_a_parser_change_recomputes(fake_world):
    first = _run(designations.build_rows([_matter()]))
    n = len(fake_world["ranges"])
    again = _run(designations.build_rows([_matter()], first))
    assert len(fake_world["ranges"]) == n and again[0]["pins"] == first[0]["pins"]
    first[0]["parser"] = dt.PARSER_VERSION - 1
    _run(designations.build_rows([_matter()], first))
    assert len(fake_world["ranges"]) == n + 1


def test_a_resolver_failure_raises_and_is_never_stored_as_no_parcels(monkeypatch):
    monkeypatch.setattr(address_points, "pins_in_range", AsyncMock(side_effect=RuntimeError("Address Points down")))
    with pytest.raises(RuntimeError):
        _run(designations.build_rows([_matter()]))


# --- per parcel ------------------------------------------------------------------------------------------------------

def _row(**over) -> dict:
    row = {
        "record": "O2026-0027059", "passed_on": "2026-09-23", "url": "https://clerk/x", "title": "t", "parser": dt.PARSER_VERSION,
        "parse": {"status": "clean", "name": "Bryn Mawr Avenue District", "kind": "district", "notes": [],
                  "segments": [{"dir": "W", "name": "BRYN MAWR", "type": "AVE", "lo": 900, "hi": 1199, "side": "both", "raw": "x"}]},
        "pins": [["17000000000001", 41.9, -87.66], ["17000000000002", 41.9, -87.66]], "unresolved": [],
    }
    row.update(over)
    return row


def _snap(*rows, status="ok", checked="2026-10-22T10:00:00Z"):
    return {"status": status, "checked_at": checked, "vintage": "2026-06-17", "designations": list(rows)}


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setattr(currency, "_now", lambda now=None: NOW)


def _match(snap, pin="17000000000001", address="1010 W Bryn Mawr Ave", reg=None, today=TODAY):
    return designations.matches_for(pin, address, reg, snapshot=snap, today=today)


def test_a_parcel_on_a_listed_block_is_flagged_by_pin_in_the_listings_own_words():
    (h,) = _match(_snap(_row()))
    assert (h["record"], h["passed_on"], h["matched_by"], h["kind"], h["map_checked"]) == ("O2026-0027059", "2026-09-23", "pin", "district", True)
    assert h["name"] == "Bryn Mawr Avenue District" and h["segment"] == "900-1199 W Bryn Mawr Ave"


def test_an_unresolved_pin_is_matched_on_the_address_and_an_off_block_address_is_not():
    (h,) = _match(_snap(_row()), pin=None)
    assert h["matched_by"] == "address"
    assert _match(_snap(_row()), pin=None, address="1200 W Bryn Mawr Ave") == []   # the next block
    assert _match(_snap(_row()), pin=None, address="1010 W Foster Ave") == []
    assert _match(_snap(_row()), pin="17999999999999", address=None) == []        # a pin the ordinance does not list, no address


def test_a_parcel_the_map_already_shows_as_a_landmark_gets_nothing_added():
    for reg in (RegulatorySummary(is_landmark_building=True), RegulatorySummary(in_landmark_district=True)):
        assert _match(_snap(_row()), reg=reg) == []
    assert len(_match(_snap(_row()), reg=RegulatorySummary())) == 1                  # checked, not a landmark: the news stands


def test_when_the_landmark_layers_did_not_answer_the_words_do_not_claim_the_map_says_no():
    reg = RegulatorySummary(unchecked_overlays=["landmark_building"])
    (h,) = _match(_snap(_row()), reg=reg)
    assert h["map_checked"] is False
    assert "could not be checked today" in landmark_designation_text(h) and "did not show" not in landmark_designation_text(h)
    other = RegulatorySummary(unchecked_overlays=["adu_area"])                        # an unrelated layer: the landmark answer stands
    assert _match(_snap(_row()), reg=other)[0]["map_checked"] is True


def test_the_lookback_is_inclusive_and_a_clean_parse_is_required():
    last_day = date.fromordinal(TODAY.toordinal() - designations.LOOKBACK_DAYS).isoformat()
    after = date.fromordinal(TODAY.toordinal() - designations.LOOKBACK_DAYS - 1).isoformat()
    assert len(_match(_snap(_row(passed_on=last_day)))) == 1
    assert _match(_snap(_row(passed_on=after))) == []
    assert _match(_snap(_row(passed_on="2026-10-23"))) == []                          # not yet passed: never
    assert _match(_snap(_row(parse={**_row()["parse"], "status": "partial"}))) == []


def test_an_untrustworthy_snapshot_says_nothing():
    assert _match(_snap(_row(), status="failed")) == []
    assert _match(_snap(_row(), checked="2026-09-01T10:00:00Z")) == []                # older than 14 days: a stale list may be past the map
    # no snapshot at all (never synced; conftest points the file at a missing one)
    assert designations.matches_for("17000000000001", "1010 W Bryn Mawr Ave", None, today=TODAY) == []
    assert _match({"status": "ok", "checked_at": "2026-10-22T10:00:00Z"}) == []       # a schema-2 snapshot has no designations


def test_newest_first():
    older = _row(record="O2026-1", passed_on="2026-08-01")
    hits = _match(_snap(older, _row()))
    assert [h["record"] for h in hits] == ["O2026-0027059", "O2026-1"]


# --- the words -------------------------------------------------------------------------------------------------------------

def test_a_building_note_says_listing_this_address_never_that_it_is_a_landmark():
    hit = {"record": "O2026-0026117", "passed_on": "2026-07-15", "url": "https://clerk/y", "name": "Chicago Daily News Building",
           "kind": "building", "segment": "2 N Riverside Plz", "map_checked": True, "matched_by": "pin"}
    text = landmark_designation_text(hit)
    assert "listing this address" in text and "Chicago Daily News Building (O2026-0026117)" in text and "Jul 15, 2026" in text
    assert "did not show this parcel as a landmark" in text and "§2-120-740" in text
    assert "is a Chicago Landmark" not in text and "has been designated" not in text


def test_a_district_note_says_the_blocks_and_that_the_boundary_is_in_the_ordinance():
    hit = {"record": "O2026-0027059", "passed_on": "2026-09-23", "url": "u", "name": "Bryn Mawr Avenue District", "kind": "district",
           "segment": "900-1199 W Bryn Mawr Ave", "map_checked": True, "matched_by": "pin"}
    text = landmark_designation_text(hit)
    assert "names the blocks of 900-1199 W Bryn Mawr Ave" in text and "cannot say whether this parcel is inside it" in text


def test_the_generic_name_building_is_not_quoted_as_a_name():
    hit = {"record": "O2026-0023266", "passed_on": "2026-05-20", "url": "u", "name": "building", "kind": "building", "segment": "30 N Lasalle St", "map_checked": True}
    assert "building (O2026" not in landmark_designation_text(hit) and "O2026-0023266" in landmark_designation_text(hit)


def test_the_coverage_note_carries_the_link_the_section_and_the_facts():
    hit = {"record": "O2026-0027059", "passed_on": "2026-09-23", "url": "https://clerk/x", "name": "Bryn Mawr Avenue District",
           "kind": "district", "segment": "900-1199 W Bryn Mawr Ave", "map_checked": True, "matched_by": "pin"}
    notes = build_coverage_notes(zoning=ZoningSummary(zone_class="RM-4.5"), regulatory=None, property_=None, neighborhood=None, adu=None,
                                 code_vintage=None, passed_landmark_designations=[hit])
    n = next(x for x in notes if x["id"] == "landmark_designation_passed")
    assert n["applies"] == "parcel" and n["link"] == "https://clerk/x" and n["section"] == "2-120-740"
    assert n["params"]["record"] == "O2026-0027059" and n["params"]["kind"] == "district"


# --- on a parcel's context ---------------------------------------------------------------------------------------------------

def _ctx(monkeypatch, snap, **kw):
    monkeypatch.setattr(currency, "load_snapshot", lambda: snap)
    return ContextObject(resolved_address="1010 W Bryn Mawr Ave", parcel_pin="17000000000001",
                         parcel_zoning=ZoningSummary(zone_class="RM-4.5"), regulatory=RegulatorySummary(), **kw)


def test_the_context_carries_the_match_and_its_coverage_note(monkeypatch):
    ctx = _ctx(monkeypatch, _snap(_row()))
    assert [h["record"] for h in ctx.passed_landmark_designations] == ["O2026-0027059"]
    assert any(n["id"] == "landmark_designation_passed" for n in ctx.coverage_notes)
    assert "passed_landmark_designations" in ctx.model_dump(exclude_none=True)


def test_a_landmark_the_map_shows_removes_the_match_from_the_context(monkeypatch):
    ctx = _ctx(monkeypatch, _snap(_row()))
    ctx.regulatory = RegulatorySummary(in_landmark_district=True)
    assert ctx.passed_landmark_designations is None
    assert not any(n["id"] == "landmark_designation_passed" for n in (ctx.coverage_notes or []))


def test_an_area_turn_and_an_approximate_parcel_are_not_matched_by_pin(monkeypatch):
    monkeypatch.setattr(currency, "load_snapshot", lambda: _snap(_row()))
    assert ContextObject(community_area=24).passed_landmark_designations is None      # no parcel, no address
    approx = ContextObject(resolved_address="1200 W Bryn Mawr Ave", parcel_pin="17000000000001", parcel_resolution="approximate")
    assert approx.passed_landmark_designations is None                                # the nearest parcel's PIN is not used; the address is on the next block
    near = ContextObject(resolved_address="1010 W Bryn Mawr Ave", parcel_pin="17000000000001", parcel_resolution="approximate")
    assert near.passed_landmark_designations[0]["matched_by"] == "address"


# --- the daily sync ----------------------------------------------------------------------------------------------------------------

def test_the_sync_part_records_ok_and_keeps_the_previous_rows_on_failure(fake_world, monkeypatch):
    monkeypatch.setattr(clerk, "passed_since", AsyncMock(return_value=[_matter()]))
    rows, check = _run(sync._designation_part(None, NOW, None))
    assert check["status"] == "ok" and check["parser"] == dt.PARSER_VERSION and check["counts"]["flaggable"] == 1 and len(rows) == 1
    monkeypatch.setattr(address_points, "pins_in_range", AsyncMock(side_effect=RuntimeError("down")))
    prev = [_row(record="O2026-OLD")]
    kept, failed = _run(sync._designation_part({"designations": prev, "designation_check": check}, NOW, None))
    assert kept == prev and failed["status"] == "failed" and "down" in failed["last_error"] and failed["checked_at"] == check["checked_at"]


def test_a_failed_snapshot_keeps_the_designations():
    snap = sync.failed_snapshot({"designations": [_row()], "rezonings": []}, "Clerk down", now=NOW)
    assert snap["designations"] == [_row()] and snap["status"] == "failed"


def test_the_admin_status_counts_what_was_placed_and_what_was_not(monkeypatch):
    unread = _row(record="O2025-0019665", parse={"status": "unparsed", "notes": ["x"], "segments": []}, pins=[])
    nopins = _row(record="O2026-NOPIN", pins=[])
    snap = {**_snap(_row(), unread, nopins), "designation_check": {"status": "ok", "checked_at": "2026-10-22T10:00:00Z"}}
    monkeypatch.setattr(currency, "load_snapshot", lambda: snap)
    st = currency.designation_status()
    assert st["passed"] == 3 and st["with_parcels"] == 1 and st["unparsed"] == ["O2025-0019665"] and st["no_parcels"] == ["O2026-NOPIN"]
    monkeypatch.setattr(currency, "load_snapshot", lambda: None)
    assert currency.designation_status()["check_status"] == "missing" and currency.designation_status()["passed"] is None


# --- the model is told ------------------------------------------------------------------------------------------------------------------

def test_prompt_rule_39_forbids_calling_the_parcel_a_landmark():
    from backend.prompts import SYNTHESIZER_SYSTEM

    i = SYNTHESIZER_SYSTEM.index("39. LANDMARK DESIGNATIONS THE MAP DOESN'T SHOW YET")
    rule = SYNTHESIZER_SYSTEM[i:i + 2400]
    for needle in ("`passed_landmark_designations`", "listing this address", "never say the parcel IS a landmark", "§2-120-740",
                   "`map_checked` is false", "district", "Never say \"not a landmark\""):
        assert needle in rule, needle
