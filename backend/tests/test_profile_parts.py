"""The Property Profile in parts (decision Item 89): /api/profile/overview + /api/profile/part/{name}.

The contract: once every part is in, the Profile the parts assembled equals the full /api/scorecard response
for the same sources (the full response is unchanged and still serves today's Profile, chat and the report);
the Overview holds what the Overview reads; a late source past its deadline is "couldn't check in time", never
"none" or "failed"; the identity is resolved once and travels in a signed token; a lost lookup rebuilds.
"""

import asyncio
import copy
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from backend import inflight, main, profile_parts
from backend.models import (
    BlockFaceTest,
    IncentivesSummary,
    NeighborhoodSummary,
    ParcelFlags,
    RegulatorySummary,
    WalkScoreSummary,
)
from backend.retrieval import property as prop_mod

pytestmark = pytest.mark.asyncio

PIN = "14331030110000"
ADDRESS = "642 W Belden Ave"
LAT, LON = 41.9239, -87.6456  # Lincoln Park, community area 7
OUTLINE = {"type": "Polygon", "coordinates": [[[-87.6457, 41.9238], [-87.6457, 41.9240], [-87.6455, 41.9240], [-87.6457, 41.9238]]]}
RL = main.ResolvedLocation(LAT, LON, ADDRESS, PIN, "authoritative", "address_points")
SALES = [
    {"sale_date": "2021-06-01T00:00:00.000", "sale_price": "910000", "deed_type": "Warranty",
     "sale_filter_less_than_10k": False, "sale_filter_deed_type": False, "is_multisale": False},
    {"sale_date": "2019-03-01T00:00:00.000", "sale_price": "1", "deed_type": "Quit Claim",
     "sale_filter_less_than_10k": True, "sale_filter_deed_type": True, "is_multisale": False},
    {"sale_date": "2001-01-01T00:00:00.000", "sale_price": "200000", "deed_type": "Warranty"},
]
WALK = WalkScoreSummary(walk_score=91, walk_description="Walker's Paradise")
FLAGS = ParcelFlags(scofflaw=True)
INC_MEMBER = IncentivesSummary(in_tif_district=True, tif_name="Fullerton/Milwaukee")
INC_FULL = IncentivesSummary(in_tif_district=True, tif_name="Fullerton/Milwaukee", tif_fund_balance=12_000_000.0)


def _zone(zone_class):
    return {"zone_class": zone_class, "zone_type": 1, "ordinance_num": None, "application_num": None,
            "ordinance_date": None, "map_updated": None, "clerk_url": None}


def _sources(*, zone_class="RS-3", crime_sleep=0.0, block_face_exc=None, rl=RL):
    """Every source both paths read, with the same answers for both."""
    stack = ExitStack()
    p = stack.enter_context
    # identity
    p(patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)))
    p(patch("backend.retrieval.property.address_points.address_point_pins", new=AsyncMock(return_value=[PIN])))
    p(patch("backend.retrieval.property.parcel_addresses.assessor_address_pins", new=AsyncMock(return_value=[PIN])))
    # property
    p(patch.object(prop_mod, "lookup_parcel_by_pin", new=AsyncMock(
        return_value={"pin14": PIN, "address": "642 W BELDEN AVE", "bldg_class": "211", "land_sqft": None,
                      "zip_code": "60614"})))
    p(patch.object(prop_mod, "get_characteristics", new=AsyncMock(
        return_value={"char_land_sf": "3100", "char_bldg_sf": "2400", "char_apts": "Two", "char_yrblt": "1890",
                      "char_type_resd": "2 Story"})))
    p(patch.object(prop_mod, "get_assessments", new=AsyncMock(
        return_value=[{"class": "211", "year": "2024", "certified_tot": "90000", "certified_land": "30000",
                       "certified_bldg": "60000"}])))
    p(patch.object(prop_mod, "get_sales", new=AsyncMock(return_value=SALES)))
    p(patch.object(prop_mod, "_fetch_building_fallbacks", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.appeals.get_appeals", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.tax_estimate.estimate_tax", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.parcel_geometry.get_parcel_geometry_facts", new=AsyncMock(
        return_value={"land_sqft_geom": 3125, "parcel_geometry": OUTLINE, "geom_year": 2024, "shared_outline_with": 0})))
    p(patch("backend.retrieval.property.parcel_flags.get_parcel_flags", new=AsyncMock(return_value=FLAGS)))
    p(patch("backend.retrieval.property.assessor_permits.get_assessor_permits", new=AsyncMock(return_value=None)))
    # the other domains
    p(patch.object(main, "regulatory_domain", new=AsyncMock(return_value=RegulatorySummary(in_tod_area=True))))
    p(patch.object(main, "lookup_zoning", new=AsyncMock(return_value=_zone(zone_class))))
    p(patch.object(main, "incentives_domain", new=AsyncMock(return_value=INC_FULL)))
    p(patch("backend.retrieval.incentives.incentives_membership", new=AsyncMock(return_value=INC_MEMBER)))
    p(patch.object(main, "neighborhood_domain", new=AsyncMock(return_value=NeighborhoodSummary(walkscore=WALK))))
    p(patch("backend.retrieval.neighborhood.walkscore_summary", new=AsyncMock(
        return_value=NeighborhoodSummary(walkscore=WALK))))
    p(patch.object(main, "aro_housing_by_community_area", new=AsyncMock(return_value=[])))

    crime_cache: list = []

    async def crime_rows(_ca):  # slow the first time, then "cached", as the real lookup is
        if not crime_cache:
            await asyncio.sleep(crime_sleep)
            crime_cache.append([])
        return []

    p(patch.object(main.crime, "crime_by_community_area", new=crime_rows))
    p(patch.object(main.crime, "crime_yoy_by_community_area", new=AsyncMock(return_value=None)))
    p(patch.object(main, "_address_violations_data", new=AsyncMock(
        return_value={"checked": True, "status_counts": [], "detail": []})))
    p(patch.object(main.three11, "address_311_complaints", new=AsyncMock(return_value=None)))
    p(patch("backend.retrieval.property.sales.nearby_comparable_sales", new=AsyncMock(return_value={"sales": []})))
    p(patch("backend.retrieval.property.block_face.block_face_test", new=AsyncMock(
        return_value=BlockFaceTest(state="met", lots=8, counted=8, two_plus=6), side_effect=block_face_exc)))
    return stack


def _without_arms_length(profile: dict) -> dict:
    out = copy.deepcopy(profile)
    for row in ((out.get("context") or {}).get("property") or {}).get("sales_history") or []:
        row.pop("arms_length", None)
    return out


async def _all_parts(address=ADDRESS):
    ov = await profile_parts.overview(address, None, None, None)
    responses = [ov]
    for name in ov["parts_pending"]:
        responses.append(await profile_parts.part(name, ov["lookup"], None))
    return ov, responses


@pytest.fixture(autouse=True)
def _reset():
    profile_parts._reset_for_tests()
    yield
    inflight._reset_for_tests()


@pytest.mark.parametrize("zone_class,block_face_exc", [("RS-3", None), ("RS-3", RuntimeError("down")), ("B3-2", None)])
async def test_the_parts_together_equal_the_full_profile(zone_class, block_face_exc):
    with _sources(zone_class=zone_class, block_face_exc=block_face_exc):
        full = await main._scorecard_payload(ADDRESS, None, None, None)
        _ov, responses = await _all_parts()
    last = max(responses, key=lambda r: r["version"])
    assert last["parts_pending"] == []
    assert _without_arms_length(last["profile"]) == full


async def test_the_overview_holds_what_the_overview_reads_and_names_the_rest():
    with _sources():
        ov = await profile_parts.overview(ADDRESS, None, None, None)
    prof = ov["profile"]
    ctx = prof["context"]
    assert prof["resolved_pin"] == PIN and prof["resolved_confidence"] == "authoritative"
    assert ctx["parcel_zoning"]["zone_class"] == "RS-3"
    assert prof["zone_definition"]["zone_class"] == "RS-3"
    assert ctx["property"]["land_sqft"] == 3100 and ctx["property"]["units"] == 2
    assert ctx["neighborhood"]["walkscore"]["walk_score"] == 91
    assert ctx["incentives"]["in_tif_district"] is True  # the verdict's membership
    assert "tif_fund_balance" not in ctx["incentives"]  # the TIF reports are a late part
    assert "flags" not in ctx["property"]  # History
    assert "crime_last_90d" not in ctx and prof["comparables"] is None
    assert prof["partial_failures"] == []  # not asked yet is not a failure
    assert ov["parts_in"] == ["overview"]
    assert ov["parts_pending"] == ["history", "money", "incentives", "neighborhood", "activity", "block_face"]


async def test_each_sale_carries_the_countys_arms_length_call():
    with _sources():
        ov = await profile_parts.overview(ADDRESS, None, None, None)
        full = await main._scorecard_payload(ADDRESS, None, None, None)
    rows = ov["profile"]["context"]["property"]["sales_history"]
    assert [r["arms_length"] for r in rows] == [True, False, None]
    assert all("arms_length" not in r for r in full["context"]["property"]["sales_history"])


@pytest.mark.parametrize("row,expected", [
    ({"sale_filter_less_than_10k": "false", "sale_filter_deed_type": "false", "is_multisale": "false"}, True),
    ({"sale_filter_less_than_10k": "false", "sale_filter_deed_type": "true", "is_multisale": "false"}, False),
    ({"sale_filter_less_than_10k": "false", "sale_filter_deed_type": "false", "is_multisale": True}, False),
    ({"sale_filter_less_than_10k": "true"}, False),
    ({"sale_filter_less_than_10k": "false"}, None),
    ({}, None),
])
async def test_arms_length_reads_the_three_county_filters(row, expected):
    assert prop_mod.arms_length(row) is expected


async def test_a_late_source_past_its_deadline_is_named_and_a_retry_finds_it(monkeypatch):
    monkeypatch.setattr(profile_parts, "LATE_DEADLINE_S", 0.05)
    with _sources(crime_sleep=0.3):
        ov = await profile_parts.overview(ADDRESS, None, None, None)
        late = await profile_parts.part("activity", ov["lookup"], None)
        assert late["timed_out"] == ["crime"]
        assert late["timed_out_by_part"] == {"activity": ["crime"]}
        # never "failed", never "none": the crime figures are just absent and the failure list doesn't name it
        assert "crime_last_90d" not in late["profile"]["context"]
        assert late["profile"]["partial_failures"] == []
        assert inflight.in_flight() >= 1  # the fetch kept running past the deadline
        await asyncio.sleep(0.4)
        retry = await profile_parts.part("activity", ov["lookup"], None)
    assert retry["timed_out"] == []
    assert retry["timed_out_by_part"] == {}
    assert retry["version"] > late["version"]


async def test_the_first_screen_and_the_overview_resolve_once():
    with _sources() as _s:
        calls = 0

        async def slow_resolve(*_a, **_k):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return RL

        with patch.object(main, "_resolve_location", new=slow_resolve):
            first, ov = await asyncio.gather(
                main.scorecard_first(address=ADDRESS), profile_parts.overview(ADDRESS, None, None, None),
            )
    assert calls == 1
    assert first["resolved_pin"] == ov["profile"]["resolved_pin"] == PIN
    assert first["lot"]["land_sqft"] == ov["profile"]["context"]["property"]["land_sqft"]


async def test_a_bad_or_expired_lookup_is_a_409(monkeypatch):
    with _sources():
        ov = await profile_parts.overview(ADDRESS, None, None, None)
    body, mac = ov["lookup"].split(".")
    with pytest.raises(main.HTTPException) as e:
        await profile_parts.part("history", body + "." + mac[:-2] + "AA", None)
    assert e.value.status_code == 409
    claims = profile_parts.read_lookup(ov["lookup"])
    claims["exp"] = 0
    with pytest.raises(main.HTTPException) as e:
        await profile_parts.part("history", profile_parts.sign_lookup(claims), None)
    assert e.value.status_code == 409
    with pytest.raises(main.HTTPException) as e:
        await profile_parts.part("nonsense", ov["lookup"], None)
    assert e.value.status_code == 404


async def test_a_lookup_the_server_lost_is_rebuilt_with_the_parts_the_page_has():
    with _sources():
        full = await main._scorecard_payload(ADDRESS, None, None, None)
        ov = await profile_parts.overview(ADDRESS, None, None, None)
        for name in ("history", "money", "incentives", "neighborhood", "block_face"):
            await profile_parts.part(name, ov["lookup"], None)
        profile_parts._records._store.clear()  # a restart
        last = await profile_parts.part("activity", ov["lookup"], "history,money,incentives,neighborhood,block_face")
    assert last["parts_pending"] == []
    assert _without_arms_length(last["profile"]) == full


async def test_an_approximate_match_is_reconciled_once_and_the_token_carries_it():
    approx = main.ResolvedLocation(LAT, LON, ADDRESS, None, "approximate", "geocode_nearest")
    with _sources(rl=approx), \
            patch.object(prop_mod, "lookup_parcel", new=AsyncMock(
                return_value={"pin14": PIN, "address": "642 W BELDEN AVE", "bldg_class": "211"})), \
            patch("backend.retrieval.property.address_points.parcel_address_matches",
                  new=AsyncMock(return_value=True)) as round_trip:
        full = await main._scorecard_payload(ADDRESS, None, None, None)
        round_trip.reset_mock()
        _ov, responses = await _all_parts()
    assert round_trip.await_count == 1  # the Overview, never the late parts
    last = max(responses, key=lambda r: r["version"])
    assert last["profile"]["resolved_confidence"] == "authoritative"
    assert _without_arms_length(last["profile"]) == full


async def test_shared_runs_once_and_cancels_only_when_nobody_waits():
    started = 0

    async def work():
        nonlocal started
        started += 1
        await asyncio.sleep(0.2)
        return "done"

    a = asyncio.create_task(inflight.shared("k", work))
    b = asyncio.create_task(inflight.shared("k", work))
    await asyncio.sleep(0.01)
    a.cancel()  # one visitor leaves; the other still waits
    assert await b == "done"
    assert started == 1
    c = asyncio.create_task(inflight.shared("k2", work))
    await asyncio.sleep(0.01)
    c.cancel()
    await asyncio.sleep(0.01)
    assert inflight.in_flight() == 0  # nobody waits: the call is cancelled


async def test_the_overview_endpoint_and_a_part_are_routed():
    import httpx

    transport = httpx.ASGITransport(app=main.app)  # no lifespan: the app's startup loads models over the network
    with _sources():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ov = await client.get("/api/profile/overview", params={"address": ADDRESS})
            assert ov.status_code == 200, ov.text
            body = ov.json()
            part = await client.get("/api/profile/part/history", params={"lookup": body["lookup"]})
            assert part.status_code == 200, part.text
            assert part.json()["profile"]["context"]["property"]["flags"]["scofflaw"] is True


async def test_building_facts_start_before_the_parcel_flags_answer():
    """Item 81, point 4: the fallback used to wait for the whole first batch, parcel flags included (6.5 s p50)."""
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    started_at: list[float] = []

    async def slow_flags(*_a, **_k):
        await asyncio.sleep(0.3)
        return None

    async def fallback(*_a, **_k):
        started_at.append(loop.time() - t0)
        return None

    with _sources(), \
            patch("backend.retrieval.property.parcel_flags.get_parcel_flags", new=slow_flags), \
            patch.object(prop_mod, "_fetch_building_fallbacks", new=fallback):
        summary = await prop_mod.property_domain(LAT, LON, pin=PIN, workflow="property_intelligence")
    assert summary is not None and started_at and started_at[0] < 0.2


async def test_an_exact_pin_starts_the_core_lookups_beside_the_parcel_row():
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    chars_at: list[tuple[str, float]] = []

    async def slow_row(pin, **_k):
        await asyncio.sleep(0.2)
        return {"pin14": PIN, "address": "642 W BELDEN AVE", "bldg_class": "211"}

    async def chars(pin14, **_k):
        chars_at.append((pin14, loop.time() - t0))
        return {"char_land_sf": "3100"}

    with _sources(), patch.object(prop_mod, "lookup_parcel_by_pin", new=slow_row), \
            patch.object(prop_mod, "get_characteristics", new=chars):
        summary = await prop_mod.property_core(LAT, LON, pin=PIN, workflow="property_intelligence")
    assert summary.land_sqft == 3100
    assert chars_at[0][0] == PIN and chars_at[0][1] < 0.1  # didn't wait for the 0.2 s parcel row


async def test_a_parcel_row_naming_another_parcel_redoes_the_core_for_that_parcel():
    other = "14331030120000"
    asked: list[str] = []

    async def chars(pin14, **_k):
        asked.append(pin14)
        return {"char_land_sf": "3100" if pin14 == other else "9999"}

    with _sources(), \
            patch.object(prop_mod, "lookup_parcel_by_pin", new=AsyncMock(return_value=None)), \
            patch.object(prop_mod, "lookup_parcel", new=AsyncMock(
                return_value={"pin14": other, "address": "644 W BELDEN AVE", "bldg_class": "211"})), \
            patch.object(prop_mod, "get_characteristics", new=chars):
        summary = await prop_mod.property_domain(LAT, LON, pin=PIN, workflow="property_intelligence")
    assert summary.pin14 == other and summary.land_sqft == 3100
    assert asked[-1] == other


async def test_the_deadline_counts_the_sources_own_time_not_its_queue(monkeypatch):
    """Late sources wait for a slot (LATE_CONCURRENCY); the 20 s is each source's own time."""
    monkeypatch.setattr(profile_parts, "LATE_CONCURRENCY", 1)
    profile_parts._reset_for_tests()

    async def slow(_tag):
        await asyncio.sleep(0.15)
        return _tag

    got = await asyncio.gather(*(
        profile_parts._late_source(("q", i), (lambda i=i: slow(i)), 0.3) for i in range(3)
    ))
    # one at a time: the third waited 0.3 s for its slot, but ran 0.15 s, within its deadline
    assert got == [(True, 0), (True, 1), (True, 2)]
