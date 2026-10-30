"""V3: "which parcel did you resolve?" - the record behind the Profile's PIN.

Real cases (queried 2026-10-02) the record has to explain: P5's address maps to 3
parcels in the Assessor's data but one in Address Points; P3's two official sources
name DIFFERENT parcels; P2 (a vacant lot) has no address point at all and resolves via
the Assessor; P4's PIN is a building the Parcel Universe doesn't hold."""

from unittest.mock import AsyncMock, patch

import pytest

from backend import main
from backend.models import ContextObject, PropertySummary
from backend.resolution import build_resolution, parcel_centroid
from backend.retrieval.property import address_points, parcel_addresses

P5_PINS = ["14313320160000", "14313320170000", "14313320180000"]
SQUARE = {"type": "Polygon", "coordinates": [[[-87.6890, 41.9045], [-87.6890, 41.9049], [-87.6886, 41.9049], [-87.6886, 41.9045], [-87.6890, 41.9045]]]}


def _res(**kw):
    base = dict(address="1601 N Milwaukee Ave", method="address_points", lat=41.9047, lon=-87.6888, pin=P5_PINS[2], confidence="authoritative")
    base.update(kw)
    return build_resolution(**base)


# --- the record -------------------------------------------------------------------------

def test_an_address_that_maps_to_three_parcels_lists_them_and_marks_the_one_used():
    r = _res(ap_pins=[P5_PINS[2]], assessor_pins=P5_PINS)
    assert [c["pin"] for c in r["candidates"]] == P5_PINS
    assert [c["used"] for c in r["candidates"]] == [False, False, True]
    assert r["candidates"][2]["sources"] == ["address_points", "assessor_addresses"]
    assert r["candidates"][0]["sources"] == ["assessor_addresses"]
    assert r["multiple_parcels"] is True and r["sources_disagree"] is False  # AP's parcel is among the Assessor's


def test_two_sources_naming_different_parcels_is_flagged_not_hidden():
    r = _res(address="1500 W Wilson Ave", pin="14171060250000", ap_pins=["14171060250000"], assessor_pins=["14171060440000"])
    assert r["sources_disagree"] is True and r["multiple_parcels"] is True
    assert {c["pin"]: c["used"] for c in r["candidates"]} == {"14171060250000": True, "14171060440000": False}


def test_a_single_agreed_parcel_is_not_a_multi_parcel_address():
    r = _res(pin="16012280180000", ap_pins=[], assessor_pins=["16012280180000"], method="assessor_addresses")
    assert r["multiple_parcels"] is False and r["sources_disagree"] is False
    assert r["candidates"] == [{"pin": "16012280180000", "sources": ["assessor_addresses"], "used": True}]


def test_a_pin_or_point_the_user_gave_has_no_address_candidates():
    for method in ("pin", "coordinates"):
        r = _res(address=None, method=method, ap_pins=[], assessor_pins=[])
        assert r["candidates"] == [] and r["multiple_parcels"] is False


def test_the_point_basis_says_where_the_point_came_from():
    basis = {m: _res(method=m)["point_basis"] for m in ("coordinates", "pin", "address_points", "assessor_addresses", "geocode_nearest", "geocode_nearest_verified")}
    assert basis == {"coordinates": "given", "pin": "parcel_centroid", "address_points": "address_point",
                     "assessor_addresses": "parcel_centroid", "geocode_nearest": "geocode", "geocode_nearest_verified": "geocode"}
    assert _res(method=None)["point_basis"] is None


def test_distance_from_the_matched_point_to_the_parcels_center():
    c = parcel_centroid(SQUARE)
    assert c == pytest.approx((41.9047, -87.6888), abs=1e-4)
    assert _res(lat=41.9047, lon=-87.6888, parcel_geometry=SQUARE)["centroid_gap_ft"] <= 3
    far = _res(lat=41.9047 + 0.0005, lon=-87.6888, parcel_geometry=SQUARE)["centroid_gap_ft"]
    assert 170 <= far <= 190  # ~0.0005 deg of latitude is ~182 ft
    assert _res(parcel_geometry=None)["centroid_gap_ft"] is None
    assert _res(parcel_geometry={"type": "nonsense"})["centroid_gap_ft"] is None


def test_a_condominium_building_is_not_reported_as_a_source_disagreement():
    """P4: Address Points holds the building PIN (...0000); the Assessor lists the units."""
    units = [f"1710135039{n:04d}" for n in range(1001, 1051)]
    r = _res(address="401 N Wabash Ave", pin="17101350390000", ap_pins=["17101350390000"], assessor_pins=["17101350330000", *units])
    assert r["condo_units"] == 50 and r["sources_disagree"] is False and r["multiple_parcels"] is True
    assert len(r["candidates"]) == 52 and [c["pin"] for c in r["candidates"] if c["used"]] == ["17101350390000"]
    # an ordinary two-source disagreement and a lone unit-looking PIN are not condos
    assert _res(pin="14171060250000", ap_pins=["14171060250000"], assessor_pins=["14171060440000"])["condo_units"] == 0
    assert _res(pin="17101350390000", ap_pins=["17101350390000"], assessor_pins=["17101350391001"])["condo_units"] == 0


def test_an_unconfirmed_identity_says_why_and_names_the_other_parcel():
    r = _res(address="401 N Wabash Ave", pin="17101350390000", ap_pins=["17101350390000"], unverified=True,
             unverified_reason="property_record_is_another_parcel", property_pin="17101350382166")
    assert r["identity_unconfirmed"] is True
    assert r["unverified_reason"] == "property_record_is_another_parcel" and r["property_record_pin"] == "17101350382166"
    ok = _res()
    assert ok["identity_unconfirmed"] is False and ok["unverified_reason"] is None and ok["property_record_pin"] is None


# --- the two address sources, returning EVERY pin -------------------------------------------

@pytest.mark.asyncio
async def test_address_points_returns_every_distinct_well_formed_pin():
    rows = [{"pin": "14313320180000"}, {"pin": "14-31-332-017-0000"}, {"pin": "14313320180000"},
            {"pin": "1433314059000"}, {"pin": "00000000000000"}]  # a duplicate, a corrupt 13-digit PIN, a null PIN
    with patch.object(address_points, "socrata_get", new=AsyncMock(return_value=rows)):
        assert await address_points.address_point_pins("1601 N Milwaukee Ave") == ["14313320170000", "14313320180000"]


@pytest.mark.asyncio
async def test_address_points_pins_empty_on_error_unparseable_or_no_rows():
    with patch.object(address_points, "socrata_get", new=AsyncMock(side_effect=RuntimeError("down"))):
        assert await address_points.address_point_pins("9999 N Nowhere Ave") == []
    assert await address_points.address_point_pins("not an address") == []
    with patch.object(address_points, "socrata_get", new=AsyncMock(return_value=[])):
        assert await address_points.address_point_pins("9998 N Nowhere Ave") == []


@pytest.mark.asyncio
async def test_assessor_pins_use_the_newest_year_with_an_exact_address_match():
    rows = [
        {"pin": "14313320160000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025.0"},
        {"pin": "14313320170000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025"},
        {"pin": "14313320180000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025"},
        {"pin": "14313320999999", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2019"},  # older year: ignored
        {"pin": "14313320111111", "prop_address_full": "1601 N MILWAUKEEWOOD AVE", "year": "2025"},  # a different street
    ]
    with patch.object(parcel_addresses, "socrata_get", new=AsyncMock(return_value=rows)):
        assert await parcel_addresses.assessor_address_pins("1601 N Milwaukee Ave") == P5_PINS


@pytest.mark.asyncio
async def test_a_year_the_portal_spells_two_ways_is_one_year():
    """Latent bug found while building V3: "2025.0" and "2025" were separate buckets, so a
    multi-parcel address could resolve to ONE of its parcels with false confidence."""
    rows = [{"pin": "14313320160000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025.0"},
            {"pin": "14313320170000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025"}]
    with patch.object(parcel_addresses, "socrata_get", new=AsyncMock(return_value=rows)):
        assert await parcel_addresses.assessor_address_to_pin("1601 N Milwaukee Ave") is None  # two parcels, not one
    assert parcel_addresses._year_key("2025.0") == parcel_addresses._year_key("2025") == "2025"
    assert parcel_addresses._year_key(None) == "" and parcel_addresses._year_key("n/a") == "n/a"


@pytest.mark.asyncio
async def test_assessor_pins_empty_on_error():
    with patch.object(parcel_addresses, "socrata_get", new=AsyncMock(side_effect=RuntimeError("down"))):
        assert await parcel_addresses.assessor_address_pins("9997 N Nowhere Ave") == []


@pytest.mark.asyncio
async def test_the_single_pin_resolvers_still_refuse_a_multi_pin_address():
    """The refactor shares the query and filters; the confidence rule is unchanged."""
    rows = [{"pin": "14313320160000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025"},
            {"pin": "14313320170000", "prop_address_full": "1601 N MILWAUKEE AVE", "year": "2025"}]
    with patch.object(parcel_addresses, "socrata_get", new=AsyncMock(return_value=rows)):
        assert await parcel_addresses.assessor_address_to_pin("1601 N Milwaukee Ave") is None
    ap_rows = [{"pin": "14313320160000", "lat": "41.9", "long": "-87.6"}, {"pin": "14313320170000", "lat": "41.9", "long": "-87.6"}]
    with patch.object(address_points, "socrata_get", new=AsyncMock(return_value=ap_rows)):
        assert await address_points.address_to_pin("1601 N Milwaukee Ave") is None


# --- the method is recorded by the resolver -----------------------------------------------------

@pytest.mark.asyncio
async def test_resolver_records_how_it_found_the_parcel():
    hit = {"pin14": "14171060250000", "lat": 41.96, "lon": -87.66}
    with patch("backend.retrieval.property.address_points.address_to_pin", new=AsyncMock(return_value=hit)):
        assert (await main._resolve_location("1500 W Wilson Ave")).method == "address_points"
    with patch("backend.retrieval.property.address_points.address_to_pin", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_to_pin", new=AsyncMock(return_value="16012280180000")), \
         patch("backend.retrieval.socrata.socrata_get", new=AsyncMock(return_value=[{"lat": "41.9", "lon": "-87.6"}])):
        rl = await main._resolve_location("1256 N Artesian Ave")
        assert (rl.method, rl.pin, rl.confidence) == ("assessor_addresses", "16012280180000", "authoritative")
    with patch("backend.retrieval.property.address_points.address_to_pin", new=AsyncMock(return_value=None)), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_to_pin", new=AsyncMock(return_value=None)), \
         patch.object(main, "geocode_address", new=AsyncMock(return_value=(41.9, -87.7))):
        rl = await main._resolve_location("1 N Nowhere St")
        assert (rl.method, rl.pin, rl.confidence) == ("geocode_nearest", None, "approximate")
    rl = await main._resolve_location(lat=41.9, lon=-87.7)
    assert rl.method == "coordinates"


# --- the endpoint payload ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scorecard_payload_carries_the_resolution_record():
    rl = main.ResolvedLocation(41.9047, -87.6888, "1601 N Milwaukee Ave", P5_PINS[2], "authoritative", "address_points")
    prop = PropertySummary(pin14=P5_PINS[2], parcel_geometry=SQUARE)
    data = {"context": ContextObject(property=prop), "comparables": None}
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)), \
         patch("backend.retrieval.property.address_points.address_point_pins", new=AsyncMock(return_value=[P5_PINS[2]])), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_pins", new=AsyncMock(return_value=P5_PINS)):
        out = await main.scorecard(address="1601 N Milwaukee Ave")
    r = out["resolution"]
    assert r["method"] == "address_points" and r["pin"] == P5_PINS[2] and r["multiple_parcels"] is True
    assert [c["pin"] for c in r["candidates"]] == P5_PINS and r["centroid_gap_ft"] is not None


@pytest.mark.asyncio
async def test_a_pin_lookup_never_asks_the_address_sources():
    rl = main.ResolvedLocation(41.9047, -87.6888, None, "16012280180000", "authoritative", "pin")
    data = {"context": ContextObject(property=PropertySummary(pin14="16012280180000")), "comparables": None}
    ap, asr = AsyncMock(return_value=[]), AsyncMock(return_value=[])
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)), \
         patch("backend.retrieval.property.address_points.address_point_pins", new=ap), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_pins", new=asr):
        out = await main.scorecard(pin="16012280180000")
    ap.assert_not_called()
    asr.assert_not_called()
    assert out["resolution"]["method"] == "pin" and out["resolution"]["candidates"] == []


@pytest.mark.asyncio
async def test_an_unconfirmed_identity_reaches_the_payload_with_its_reason():
    rl = main.ResolvedLocation(41.89, -87.62, "401 N Wabash Ave", "17101350390000", "authoritative", "address_points")
    data = {"context": ContextObject(property=PropertySummary(pin14="17101350382166")), "comparables": None}
    with patch.object(main, "_resolve_location", new=AsyncMock(return_value=rl)), \
         patch.object(main, "_fetch_scorecard_data", new=AsyncMock(return_value=data)), \
         patch("backend.retrieval.property.address_points.address_point_pins", new=AsyncMock(return_value=["17101350390000"])), \
         patch("backend.retrieval.property.parcel_addresses.assessor_address_pins", new=AsyncMock(return_value=[])):
        out = await main.scorecard(address="401 N Wabash Ave")
    r = out["resolution"]
    assert out["nearest_parcel_unverified"] is True
    assert r["identity_unconfirmed"] is True and r["unverified_reason"] == "property_record_is_another_parcel"
    assert r["property_record_pin"] == "17101350382166"
