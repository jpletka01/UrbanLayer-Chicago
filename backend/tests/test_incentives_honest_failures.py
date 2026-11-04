"""A failed or empty incentive source is "not checked", never "not in one" (decision Item 65).

Recorded responses (2026-11-03, free public endpoints): HUD's Opportunity Zone layer answering a
point inside designated tract 17031540101 and one in the Gold Coast, HUD's NMTC and QCT layers for
that tract, the FCC tract lookup at 1601 N Milwaukee, and the body ArcGIS sends with **HTTP 200**
when a query fails (an invalid field). That last one is the shape the loaders used to read as "no
features" and cache as "not designated" for 24 hours.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.data_health import failures
from backend.main import _domain_data_gaps, render_report_html
from backend.models import ContextObject, IncentivesSummary, ReportData, ZoningSummary
from backend.report_builder import _apply_mock_overrides
from backend.retrieval import geo
from backend.retrieval.incentives import incentives_domain, tif
from backend.retrieval.incentives._hud_tracts import HudLayerError
from backend.retrieval.incentives.lihtc import check_qct
from backend.retrieval.incentives.nmtc import check_nmtc
from backend.retrieval.incentives.opportunity_zones import check_opportunity_zone

FIXTURES = Path(__file__).parent / "fixtures"
ERROR_BODY = "hud_arcgis_error_body_2026-11-03.json"


def _recorded(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _client(*bodies: dict) -> AsyncMock:
    """A client that answers each GET with the next body, HTTP 200 every time (as ArcGIS does)."""
    responses = []
    for body in bodies:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = body
        responses.append(resp)
    client = AsyncMock()
    client.get.side_effect = responses
    return client


@pytest.fixture(autouse=True)
def _reset():
    tif._tif_boundaries = None  # the TTLCaches are cleared by conftest
    yield
    tif._tif_boundaries = None


# --- the HUD tract layers ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oz_point_inside_a_designated_tract_is_designated():
    client = _client(_recorded("hud_oz_point_hit_2026-11-03.json"))
    result = await check_opportunity_zone(lat=41.65095, lon=-87.60112, client=client)
    assert result == {"tract": "17031540101", "designated": True}
    params = client.get.call_args.kwargs["params"]
    assert params["geometryType"] == "esriGeometryPoint" and params["geometry"] == "-87.60112,41.65095"
    assert "where" not in params  # by point, so a 2020 tract id never meets the 2010-keyed layer


@pytest.mark.asyncio
async def test_oz_point_outside_every_designated_tract_is_a_checked_miss():
    result = await check_opportunity_zone(lat=41.91, lon=-87.6341, client=_client(_recorded("hud_oz_point_miss_2026-11-03.json")))
    assert result is None


@pytest.mark.parametrize("check", [
    lambda c: check_opportunity_zone(lat=41.65095, lon=-87.60112, client=c),
    lambda c: check_opportunity_zone("17031540101", client=c),
    lambda c: check_qct("17031540101", client=c),
    lambda c: check_nmtc("17031540101", client=c),
])
@pytest.mark.asyncio
async def test_an_arcgis_error_body_raises_and_is_not_cached(check):
    client = _client(_recorded(ERROR_BODY), _recorded(ERROR_BODY))
    with pytest.raises(HudLayerError, match="ArcGIS error"):
        await check(client)
    with pytest.raises(HudLayerError):
        await check(client)
    assert client.get.call_count == 2  # the failure was not remembered as "not designated"


@pytest.mark.asyncio
async def test_a_body_with_no_feature_list_raises():
    with pytest.raises(HudLayerError, match="no feature list"):
        await check_qct("17031540101", client=_client({"objectIdFieldName": "OBJECTID"}))


@pytest.mark.asyncio
async def test_recorded_qct_and_nmtc_answers_parse():
    qct = await check_qct("17031540101", client=_client(_recorded("hud_qct_tract_2026-11-03.json")))
    assert qct == {"tract": "17031540101", "designated": True, "name": "Census Tract 5401.01"}
    nmtc = await check_nmtc("17031540101", client=_client(_recorded("hud_nmtc_tract_2026-11-03.json")))
    assert nmtc["qualifying"] is True and nmtc["severe_distress"] is True and nmtc["poverty_rate"] == 49.2


@pytest.mark.asyncio
async def test_a_tract_the_nmtc_layer_does_not_list_is_not_checked():
    # NMTC20 lists every tract (1,331 in Cook County, 708 not qualifying), so absence is a broken lookup.
    with pytest.raises(HudLayerError, match="not in the layer"):
        await check_nmtc("17031999999", client=_client({"features": []}))


# --- the FCC tract lookup ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_recorded_fcc_answer_gives_the_2020_tract():
    body = _recorded("fcc_census_area_1601_n_milwaukee_2026-11-03.json")
    assert body["input"]["censusYear"] == "2020"
    assert await geo.resolve_census_tract(41.91011, -87.67727, client=_client(body)) == "17031241400"


@pytest.mark.asyncio
async def test_an_fcc_body_without_results_raises_and_is_not_cached():
    client = _client({"status": "error"}, {"status": "error"})
    for _ in range(2):
        with pytest.raises(RuntimeError, match="no results list"):
            await geo.resolve_census_tract(41.91011, -87.67727, client=client)
    assert client.get.call_count == 2


# --- the TIF layer -----------------------------------------------------------------------------


def _null_geometry_layer(n: int = 3) -> dict:
    # The shape the City's Enterprise Zone view took on 2026-02-23 (Item 64): features, no geometry.
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": None, "properties": {}}] * n}


@pytest.mark.asyncio
async def test_an_empty_tif_layer_raises_and_is_not_cached():
    client = _client(_null_geometry_layer(), _null_geometry_layer())
    with pytest.raises(RuntimeError, match="no usable geometry"):
        await tif.check_tif(41.91, -87.67, client=client)
    assert tif._tif_boundaries is None
    with pytest.raises(RuntimeError):
        await tif.tif_districts_by_community_area(24, client=client)
    assert client.get.call_count == 2


# --- the orchestrator --------------------------------------------------------------------------


def _patched(**overrides):
    """Patch every source the point orchestrator calls; each returns a checked miss unless overridden."""
    defaults = {
        "check_tif": None, "check_enterprise_zone": None, "resolve_census_tract": "17031241400",
        "check_opportunity_zone": None, "check_qct": None,
        "check_nmtc": {"tract": "17031241400", "qualifying": False, "severe_distress": False, "poverty_rate": 9.0},
        "fetch_tif_financials": [], "fetch_tif_fund_analysis": [],
    }
    defaults.update(overrides)
    patches = []
    for name, value in defaults.items():
        mock = AsyncMock()
        if isinstance(value, Exception):
            mock.side_effect = value
        else:
            mock.return_value = value
        patches.append(patch(f"backend.retrieval.incentives.{name}", mock))
    return patches


async def _run(**overrides) -> IncentivesSummary:
    patches = _patched(**overrides)
    for p in patches:
        p.start()
    try:
        return await incentives_domain(41.91, -87.67, client=AsyncMock())
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_a_clean_run_checks_everything():
    result = await _run()
    assert result.unchecked == [] and result.data_gaps == [] and result.enterprise_zone_unchecked is False


@pytest.mark.asyncio
async def test_a_failed_tif_layer_is_not_checked_not_not_in_a_tif():
    result = await _run(check_tif=RuntimeError("TIF boundary response has no usable geometry (0 features)"))
    assert result.in_tif_district is False
    assert result.unchecked == ["tif"] and result.data_gaps == ["TIF district"]


@pytest.mark.asyncio
async def test_a_failed_tract_lookup_leaves_qct_and_nmtc_unchecked_but_still_checks_oz_by_point():
    oz = AsyncMock(return_value={"tract": "17031540101", "designated": True})
    with patch("backend.retrieval.incentives.check_opportunity_zone", oz):
        patches = _patched(resolve_census_tract=RuntimeError("FCC down"))
        patches = [p for p in patches if "check_opportunity_zone" not in p.attribute]
        for p in patches:
            p.start()
        try:
            result = await incentives_domain(41.91, -87.67, client=AsyncMock())
        finally:
            for p in patches:
                p.stop()
    assert oz.call_args.kwargs == {"lat": 41.91, "lon": -87.67, "client": oz.call_args.kwargs["client"]}
    assert result.in_opportunity_zone is True
    assert result.unchecked == ["qct", "nmtc"]
    assert result.data_gaps == ["Qualified Census Tract", "New Markets Tax Credit tract"]


@pytest.mark.asyncio
async def test_failed_tif_finances_are_a_gap_but_the_district_itself_was_checked():
    result = await _run(
        check_tif={"tif_name": "Fullerton/Milwaukee", "properties": {}},
        fetch_tif_financials=RuntimeError("Socrata down"), fetch_tif_fund_analysis=RuntimeError("Socrata down"),
    )
    assert result.in_tif_district is True and result.unchecked == []
    assert result.data_gaps == ["TIF district finances"]


@pytest.mark.asyncio
async def test_a_failed_tif_layer_on_the_area_path_is_not_checked():
    with patch("backend.retrieval.incentives.tif_districts_by_community_area", AsyncMock(side_effect=RuntimeError("down"))):
        result = await incentives_domain(ca=24, client=AsyncMock())
    assert result.unchecked == ["tif"] and result.in_tif_district is False


# --- what each surface says ---------------------------------------------------------------------


def test_the_gap_labels_belong_to_the_incentives_key_and_the_economics_module():
    for label in failures.INCENTIVE_GAPS.values():
        assert failures.key_for_label(label) == "incentives"
    detail = failures.failed_detail(["TIF district", "Opportunity Zone"])
    assert detail == [{"key": "incentives", "labels": ["TIF district", "Opportunity Zone"]}]
    assert failures.MODULES["incentives"] == "economics"


def test_domain_gaps_carry_the_incentive_gaps_into_partial_failures():
    inc = IncentivesSummary(unchecked=["oz"], data_gaps=["Opportunity Zone"])
    assert _domain_data_gaps({"incentives": inc}, ("regulatory", "incentives")) == ["Opportunity Zone"]


def _report(unchecked: list[str]) -> ReportData:
    inc = IncentivesSummary(unchecked=unchecked, data_gaps=[failures.INCENTIVE_GAPS[k] for k in unchecked])
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_zoning=ZoningSummary(zone_class="B3-2"))
    r = _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", context=ctx, resolved_pin="14313320180000",
                                         resolved_confidence="authoritative"))
    # mock mode fills sections in; this test is about what the incentive gaps alone change
    r.context.incentives = inc
    r.partial_failures = list(inc.data_gaps)
    return r


def _financial_rows(page: str) -> str:
    start = page.index('id="section-financial"')
    return page[start:start + 6000]


def test_the_report_says_not_checked_in_each_failed_row_and_no_in_the_checked_ones():
    rows = _financial_rows(render_report_html(_report(["tif", "qct"]), "en", report_date="November 3, 2026"))
    assert 'data-testid="section-unchecked"' in rows and "TIF district" in rows
    tif_row = rows[rows.index("glossary-tif"):rows.index("glossary-oz")]
    assert "Couldn&#39;t check today" in tif_row or "Couldn't check today" in tif_row
    oz_row = rows[rows.index("glossary-oz"):rows.index("glossary-ez")]
    assert "status-no" in oz_row and "check today" not in oz_row


def test_a_healthy_report_has_no_unchecked_incentive_rows():
    rows = _financial_rows(render_report_html(_report([]), "en", report_date="November 3, 2026"))
    assert "check today" not in rows and 'data-testid="section-unchecked"' not in rows


def test_the_spanish_report_says_it_in_spanish():
    rows = _financial_rows(render_report_html(_report(["tif"]), "es", report_date="3 de noviembre de 2026"))
    assert "No se pudo verificar hoy" in rows


# --- the neighborhood parts ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failed_neighborhood_part_is_a_named_gap_and_the_rest_still_answers():
    from backend.retrieval.neighborhood import neighborhood_domain
    from backend.retrieval.neighborhood.walkscore import WalkScoreError

    settings = MagicMock(walkscore_api_key="k")
    with patch("backend.retrieval.neighborhood.get_settings", return_value=settings), \
         patch("backend.retrieval.neighborhood.fetch_walkscore", AsyncMock(side_effect=WalkScoreError("status 41"))), \
         patch("backend.retrieval.neighborhood.find_nearest_stations", AsyncMock(return_value=None)), \
         patch("backend.retrieval.neighborhood.check_tod_eligibility", AsyncMock(return_value=None)), \
         patch("backend.retrieval.neighborhood._fetch_census_tract", AsyncMock(return_value=None)), \
         patch("backend.retrieval.neighborhood.traffic.get_traffic_context", AsyncMock(return_value=None)), \
         patch("backend.retrieval.neighborhood.divvy.find_nearest_divvy", AsyncMock(side_effect=RuntimeError("down"))), \
         patch("backend.retrieval.neighborhood.ward_by_point", return_value=None):
        summary = await neighborhood_domain(41.91, -87.67, address="1601 N Milwaukee Ave", client=AsyncMock())
    assert summary.data_gaps == ["Walk Score", "Divvy stations"]  # in NEIGHBORHOOD_GAPS order
    assert summary.walkscore is None and summary.divvy is None
    assert [failures.key_for_label(g) for g in summary.data_gaps] == ["neighborhood", "neighborhood"]
    assert failures.MODULES["neighborhood"] == "area"


# --- brownfields, ARO housing, nearby construction ----------------------------------------------


@pytest.mark.asyncio
async def test_an_epa_error_body_raises_and_the_regulatory_domain_marks_brownfields_unchecked():
    from backend.retrieval.regulatory import environmental, regulatory_domain
    from backend.retrieval.regulatory.overlays import OverlayResults

    with pytest.raises(RuntimeError, match="no feature list"):
        await environmental.query_brownfield_sites(41.91, -87.67, client=_client(_recorded(ERROR_BODY)))

    with patch("backend.retrieval.regulatory.query_overlays_checked", AsyncMock(return_value=OverlayResults())), \
         patch("backend.retrieval.regulatory.query_flood_zone", AsyncMock(return_value=None)), \
         patch("backend.retrieval.regulatory.query_brownfield_sites", AsyncMock(side_effect=RuntimeError("EPA down"))):
        reg = await regulatory_domain(41.91, -87.67, client=AsyncMock())
    assert reg.brownfield_unchecked is True and reg.brownfield_sites == []
    assert _domain_data_gaps({"regulatory": reg}, ("regulatory",)) == ["EPA brownfield sites"]
    assert failures.MODULES["brownfield"] == "record"


def test_the_report_does_not_claim_a_brownfield_search_that_did_not_answer():
    from backend.models import RegulatorySummary

    r = _report([])
    r.context.regulatory = RegulatorySummary(brownfield_unchecked=True)
    page = render_report_html(r, "en", report_date="November 3, 2026")
    assert "EPA brownfield sites could not be checked" in page
    assert "Check EPA brownfield sites nearby" in page
    assert "EPA brownfield proximity search" not in page  # the "completed" checklist line
    assert "No flood/brownfield risk" not in page


@pytest.mark.asyncio
async def test_aro_and_nearby_construction_raise_instead_of_returning_none():
    from backend.retrieval import buildings
    from backend.retrieval.regulatory import aro_housing

    with patch("backend.retrieval.regulatory.aro_housing.socrata_get", AsyncMock(side_effect=RuntimeError("down"))), \
            pytest.raises(RuntimeError):
        await aro_housing.aro_housing_by_community_area(24)
    with patch("backend.retrieval.buildings.socrata_get", AsyncMock(side_effect=RuntimeError("down"))), \
            patch("backend.retrieval.buildings.socrata_aggregate", AsyncMock(side_effect=RuntimeError("down"))), \
            pytest.raises(RuntimeError):
        await buildings.nearby_new_construction(41.91, -87.67)
