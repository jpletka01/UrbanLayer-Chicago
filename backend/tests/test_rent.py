"""WS4 PR2 slice 1: the committed rent artifact, the tract-else-PUMA choice, and the pinned PUMA request."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.models import CensusTractDemographics, RentCell
from backend.retrieval.neighborhood import rent
from backend.retrieval.neighborhood.census_tract import rent_cells
from backend.retrieval.neighborhood.rent import RentArtifactError
from ingestion import build_rent_artifact as build


@pytest.fixture(autouse=True)
def _fresh_artifact():
    rent.reset_artifact()
    yield
    rent.reset_artifact()


def cell(est: int | None, moe: float | None = None) -> RentCell:
    cv = None if est is None or moe is None else round(moe / 1.645 / est, 3)
    return RentCell(estimate=est, moe=moe, cv=cv)


def tract(cells: dict[str, RentCell]) -> CensusTractDemographics:
    return CensusTractDemographics(tract_fips="17031831000", tract_name="Census Tract 8310, Cook, IL",
                                   acs_period="2020–2024", acs_release="acs2024_5yr", rent_by_bedroom=cells)


# --- the committed artifact -------------------------------------------------------------------------------


def test_artifact_covers_every_community_area_and_the_chicago_pumas():
    art = rent.load_artifact()
    assert len(art["community_areas"]) == 77
    assert len(art["tract_puma"]) == 790
    assert len(set(art["tract_puma"].values())) == 20
    assert art["acs"]["release"] == "acs2024_5yr" and art["acs"]["period"] == "2020–2024"
    assert art["method"]["key"] == "acs_handbook_median"


def test_artifact_matches_the_method_proof():
    """Decision Item 33: area 37 is a 727-household area whose margin makes it unusable, the Loop-adjacent
    areas are large and tight, and none is top-coded."""
    small = rent.community_area_rent(37)
    assert small.households == 727 and small.cv is not None and small.cv > 0.50
    big = rent.community_area_rent(24)
    assert big.median and big.cv is not None and big.cv < 0.30
    assert not any(a["top_coded"] for a in rent.load_artifact()["community_areas"].values())


def test_community_area_rent_carries_its_release_and_method():
    ca = rent.community_area_rent(24)
    assert (ca.acs_period, ca.acs_release, ca.period_end) == ("2020–2024", "acs2024_5yr", "2024-12-31")
    assert ca.moe_method == "acs_handbook_median" and ca.design_factor == build.DESIGN_FACTOR


def test_unknown_area_is_none_not_zero():
    assert rent.community_area_rent(999) is None


def test_puma_for_tract():
    assert rent.puma_for_tract(next(iter(rent.load_artifact()["tract_puma"]))).startswith("17")
    assert rent.puma_for_tract("17031999999") is None


def test_missing_artifact_raises_and_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(rent, "artifact_path", lambda: tmp_path / "rent_by_area.json")
    with pytest.raises(RentArtifactError):
        rent.community_area_rent(24)
    (tmp_path / "rent_by_area.json").write_text(json.dumps(
        {"community_areas": {"24": {"households": 10, "median": 1000, "moe": 50}}, "tract_puma": {}}))
    assert rent.community_area_rent(24).median == 1000  # the failed read left nothing behind


def test_malformed_artifact_raises(tmp_path, monkeypatch):
    (tmp_path / "rent_by_area.json").write_text('{"community_areas": []}')
    monkeypatch.setattr(rent, "artifact_path", lambda: tmp_path / "rent_by_area.json")
    with pytest.raises(RentArtifactError):
        rent.load_artifact()


# --- tract else PUMA --------------------------------------------------------------------------------------


def test_standard_tract_cell_is_used_and_names_the_tract():
    t = tract({"1_bedroom": cell(2000, 100), "2_bedrooms": cell(2400, 120), "3_bedrooms": cell(3000, 200)})
    out = rent.select_bedrooms(t, None, None, None)
    assert [b.scope for b in out] == ["tract"] * 3
    assert all(b.tract_fallback is None for b in out)
    assert out[0].geography == "Census Tract 8310, Cook, IL" and out[0].geoid == "17031831000"


def test_suppressed_and_low_tract_cells_fall_back_to_the_puma_and_say_why():
    t = tract({"1_bedroom": cell(None), "2_bedrooms": cell(2400, 1500), "3_bedrooms": cell(3000, 200)})
    puma = {"1_bedroom": cell(1900, 70), "2_bedrooms": cell(2200, 90), "3_bedrooms": cell(2800, 150)}
    out = {b.bedrooms: b for b in rent.select_bedrooms(t, puma, "West Town PUMA, IL", "1703159")}
    assert (out["1_bedroom"].scope, out["1_bedroom"].tract_fallback) == ("puma", "suppressed")
    assert (out["2_bedrooms"].scope, out["2_bedrooms"].tract_fallback) == ("puma", "low_confidence")
    assert out["3_bedrooms"].scope == "tract"
    assert out["1_bedroom"].geography == "West Town PUMA, IL" and out["1_bedroom"].geoid == "1703159"
    assert out["1_bedroom"].estimate == 1900


def test_tract_cell_is_kept_when_the_puma_could_not_be_read():
    t = tract({"1_bedroom": cell(None), "2_bedrooms": cell(2400, 1500)})
    out = {b.bedrooms: b for b in rent.select_bedrooms(t, None, None, None)}
    assert (out["1_bedroom"].scope, out["1_bedroom"].estimate, out["1_bedroom"].tract_fallback) == ("tract", None, "suppressed")
    assert out["2_bedrooms"].tract_fallback == "low_confidence"
    assert "3_bedrooms" not in out  # the tract has no such cell and there is no PUMA: nothing to say


def test_a_tract_cell_with_no_margin_is_not_standard():
    assert not rent._is_standard(RentCell(estimate=2000, moe=None, cv=None))


# --- Census Reporter ---------------------------------------------------------------------------------------


def puma_payload(release_id: str) -> dict:
    est = {"B25031001": 2098.0, "B25031002": 2003.0, "B25031003": 2049.0, "B25031004": 2155.0, "B25031005": 2171.0,
           "B25031006": 2356.0, "B25031007": 2100.0}
    err = {"B25031001": 35.0, "B25031002": 124.0, "B25031003": 67.0, "B25031004": 62.0, "B25031005": 89.0,
           "B25031006": 428.0, "B25031007": 648.0}
    return {"release": {"id": release_id}, "geography": {"79500US1703159": {"name": "West Town & Near West Side PUMA, IL"}},
            "data": {"79500US1703159": {"B25031": {"estimate": est, "error": err}}}}


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_puma_request_names_the_five_year_release():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, json=puma_payload("acs2024_5yr"))

    async with client_for(handler) as c:
        name, cells = await rent.fetch_puma_rent("1703159", "acs2024_5yr", client=c)
    assert "/data/show/acs2024_5yr" in seen[0] and "geo_ids=79500US1703159" in seen[0]
    assert name.startswith("West Town") and cells["2_bedrooms"].estimate == 2155 and cells["2_bedrooms"].moe == 62.0


async def test_puma_answer_from_another_release_is_an_error_not_a_figure():
    """Census Reporter's `latest` answers a PUMA from the 2024 1-year release; its margins are far wider."""
    async with client_for(lambda req: httpx.Response(200, json=puma_payload("acs2024_1yr"))) as c:
        with pytest.raises(RuntimeError, match="acs2024_1yr"):
            await rent.fetch_puma_rent("1703159", "acs2024_5yr", client=c)


async def test_puma_failure_is_not_cached():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=puma_payload("acs2024_5yr"))

    async with client_for(handler) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await rent.fetch_puma_rent("1703159", "acs2024_5yr", client=c)
        _, cells = await rent.fetch_puma_rent("1703159", "acs2024_5yr", client=c)
    assert cells["1_bedroom"].estimate == 2049 and len(calls) == 2


def test_rent_cells_parse_estimates_margins_and_suppression():
    data = {"B25031": {"estimate": {"B25031002": None, "B25031003": 2336.0, "B25031004": 2373.0},
                       "error": {"B25031002": None, "B25031003": 260.0, "B25031004": -555555555.0}}}
    cells = rent_cells(data)
    assert cells["no_bedroom"].estimate is None
    assert (cells["1_bedroom"].estimate, cells["1_bedroom"].moe) == (2336, 260.0)
    assert cells["1_bedroom"].cv == pytest.approx(260 / 1.645 / 2336, abs=1e-3)
    assert cells["2_bedrooms"].moe is None and cells["2_bedrooms"].cv is None  # the Census's controlled-estimate sentinel
    assert rent_cells({}) == {}


async def test_evidence_asks_for_the_puma_only_when_a_tract_cell_needs_it():
    ok = tract({g: cell(2000, 100) for g in rent.BEDROOM_GROUPS})
    ev = await rent.rent_evidence(24, ok, client=client_for(lambda r: pytest.fail("no PUMA request expected")))
    assert ev.community_area.community_area == 24 and not ev.unchecked and ev.puma_geoid is None
    assert [b.scope for b in ev.bedrooms] == ["tract"] * 3


async def test_evidence_names_a_failed_puma_request_and_keeps_the_rest(monkeypatch):
    fips = next(iter(rent.load_artifact()["tract_puma"]))
    t = tract({"1_bedroom": cell(None), "2_bedrooms": cell(2000, 100), "3_bedrooms": cell(3000, 200)})
    t.tract_fips = fips
    async with client_for(lambda req: httpx.Response(503)) as c:
        ev = await rent.rent_evidence(24, t, client=c)
    assert ev.unchecked == ["puma_rent"] and ev.community_area.median
    assert {b.bedrooms: b.scope for b in ev.bedrooms} == {"1_bedroom": "tract", "2_bedrooms": "tract", "3_bedrooms": "tract"}


async def test_evidence_without_a_tract_names_it_and_without_anything_is_none():
    ev = await rent.rent_evidence(24, None)
    assert ev.community_area is not None and ev.unchecked == ["tract_rent"] and ev.bedrooms == []
    assert await rent.rent_evidence(None, None) is None


async def test_evidence_survives_a_broken_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(rent, "artifact_path", lambda: tmp_path / "missing.json")
    t = tract({g: cell(2000, 100) for g in rent.BEDROOM_GROUPS})
    ev = await rent.rent_evidence(24, t)
    assert ev.community_area is None and "community_area_rent" in ev.unchecked and len(ev.bedrooms) == 3


# --- the builder -------------------------------------------------------------------------------------------


def test_tract_lookup_takes_the_dominant_area_and_requires_one_puma():
    rows = [("T1", "1703159", "24", 90), ("T1", "1703159", "22", 10), ("T2", "1703160", "22", 5)]
    assert build.tract_lookup(rows) == {"T1": {"puma": "1703159", "ca": "24"}, "T2": {"puma": "1703160", "ca": "22"}}
    with pytest.raises(ValueError, match="more than one PUMA"):
        build.tract_lookup([("T1", "1703159", "24", 5), ("T1", "1703160", "24", 4)])


def test_area_rent_sums_counts_before_taking_the_median():
    """Summed counts are 100 / 500 / 400, so the 500th of 1,000 households sits 400 of 500 into the middle bracket."""
    cols = [("B1", (0.0, 1000.0)), ("B2", (1000.0, 2000.0)), ("B3", (2000.0, 3000.0))]
    rows = [{"B1E": 100, "B2E": 400, "B3E": 0}, {"B1E": 0, "B2E": 100, "B3E": 400}]
    out = build.area_rent(rows, cols)
    assert out["households"] == 1000 and out["median"] == 1800 and out["moe"] and not out["top_coded"]


def test_area_rent_top_coded_has_no_median_and_no_margin():
    cols = [("B1", (0.0, 1000.0)), ("B2", (1000.0, None))]
    out = build.area_rent([{"B1E": 10, "B2E": 90}], cols)
    assert out["median"] is None and out["moe"] is None and out["top_coded"]
