"""WS0 M3: capture (ACS margins of error, comp basis, valuation year, index build date), the
figure entries built from it, and the source-date precedence."""

from __future__ import annotations

import copy
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.data_health import status
from backend.data_health.store import Store
from backend.models import (
    AddressViolations, ComparableSale, ComparablesSummary, ContextObject, EnergyBenchmark, IncentivesSummary,
    NeighborhoodSummary, ParcelFlags, PropertySummary, RegulatorySummary, ViolationSummary, ZoningSummary,
    AssessmentRecord, CensusTractDemographics, CrimeSummary, DemographicsSummary,
)
from backend.provenance import build_provenance
from backend.provenance_figures import area_benchmark_entry, source_dates, year_end
from backend.retrieval.neighborhood import census_tract as ct
from backend.retrieval.property.assessment_level import CLASS_NORM_RATE_PER_LEVEL, CLASS_NORM_TAX_YEAR
from backend.tests.test_census_tract import SAMPLE_RESPONSE

QD = "2026-10-21"


def build(ctx: ContextObject, **kw) -> dict:
    return build_provenance(context=ctx, zone_definition=None, resolved_pin=None, resolved_confidence=None, query_date=QD, **kw)


def ctx(**kw) -> ContextObject:
    kw.setdefault("parcel_zoning", ZoningSummary(zone_class="B3-2"))
    return ContextObject(**kw)


# --- ACS capture ---------------------------------------------------------------------------------------

def test_the_census_formulas_match_the_bureaus():
    # MOE of a sum: root of the summed squares.
    assert ct._moe_sum(3.0, 4.0) == 5.0 and ct._moe_sum(3.0, None) is None and ct._moe_sum() is None
    # Proportion 30 of 120 (MOEs 9 and 20): sqrt(81 - 0.0625*400)/120 = 0.0624 -> 6.2 points.
    assert ct._moe_prop(30, 9, 120, 20) == 6.2
    # A negative radicand falls back to the ratio formula (never a failure).
    assert ct._moe_prop(100, 1, 100, 50) == pytest.approx(round(((1 + 1 * 2500) ** 0.5) / 100 * 100, 1), abs=0.05)
    assert ct._moe_prop(None, 9, 120, 20) is None and ct._moe_prop(30, 9, 0, 20) is None
    # CV = standard error (MOE / 1.645) over the estimate; undefined for a zero estimate.
    assert ct._cv(2435, 220) == 0.055 and ct._cv(0, 10) is None and ct._cv(100, None) is None


def _response() -> dict:
    r = copy.deepcopy(SAMPLE_RESPONSE)
    geo = r["data"]["14000US17031242400"]
    geo["B25064"]["error"] = {"B25064001": 220.0}
    geo["B19013"]["error"] = {"B19013001": 8000.0}
    geo["B17001"]["error"] = {"B17001001": 400.0, "B17001002": 90.0}
    geo["B25002"]["error"] = {"B25002001": 100.0, "B25002003": -555555555.0}  # the Census's sentinel is not a MOE
    r["release"] = {"id": "acs2024_5yr", "years": "2020-2024"}
    return r


@pytest.mark.asyncio
async def test_the_tract_keeps_its_release_margins_of_error_and_cv():
    resp = MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value=_response()))
    client = AsyncMock()
    client.get.return_value = resp
    t = await ct.fetch_census_tract("17031242400", client=client)
    assert t.acs_release == "acs2024_5yr" and t.acs_period == "2020–2024"
    assert t.moe["median_gross_rent"] == 220.0 and t.cv["median_gross_rent"] == round(220 / 1.645 / 1850, 3)
    assert t.moe["median_household_income"] == 8000.0
    assert 0 < t.moe["poverty_rate"] < 10  # percentage points
    assert "vacancy_rate" not in t.moe  # a sentinel numerator MOE is not a margin
    assert "owner_occupied_pct" not in t.moe  # no published error on the fixture: stated as none, not invented


# --- entries from the capture -------------------------------------------------------------------------

def tract(**kw) -> CensusTractDemographics:
    base = dict(
        tract_fips="17031831000", tract_name="Census Tract 8310, Cook, IL", census_reporter_url="https://censusreporter.org/x",
        median_gross_rent=2435, poverty_rate=4.6, population=2431, acs_period="2020–2024", acs_release="acs2024_5yr",
        moe={"median_gross_rent": 220.0, "poverty_rate": 2.5}, cv={"median_gross_rent": 0.055, "poverty_rate": 0.33},
    )
    return CensusTractDemographics(**{**base, **kw})


def test_a_tract_figure_carries_its_period_margin_and_scope():
    pv = build(ctx(neighborhood=NeighborhoodSummary(census_tract=tract())))
    e = pv["area.tract.median_gross_rent"]
    assert e["precision"] == {"moe": 220.0, "moe_level": 0.9, "cv": 0.055}
    assert (e["period"], e["as_of"], e["as_of_basis"], e["scope"]) == ("2020–2024", "2024-12-31", "period_end", "tract")
    assert e["geography"] == "Census Tract 8310, Cook, IL" and e["tier"] == "official_estimate" and e["method_key"] == "survey_estimate"
    assert e["confidence"] == "standard" and e["age_days"] == 659
    assert "acs2024_5yr" in e["note"] and e["value"] == 2435


def test_a_figure_with_no_published_margin_says_none_and_a_noisy_one_is_faded():
    pv = build(ctx(neighborhood=NeighborhoodSummary(census_tract=tract(owner_occupied_pct=60.7))))
    assert pv["area.tract.owner_occupied_pct"].get("precision") is None
    poverty = pv["area.tract.poverty_rate"]
    assert poverty["confidence"] == "low" and poverty["confidence_reasons"] == ["high_cv"]
    assert "percentage points" in poverty["note"]


def test_a_cv_over_half_withholds_the_figure():
    pv = build(ctx(neighborhood=NeighborhoodSummary(census_tract=tract(poverty_rate=1.0, moe={"poverty_rate": 2.5}, cv={"poverty_rate": 0.61}))))
    assert pv["area.tract.poverty_rate"]["confidence"] == "withheld"


def test_the_community_area_income_is_a_bracket_median_and_faded():
    dm = DemographicsSummary(community_area=24, community_area_name="West Town", population=87000,
                             median_household_income=98000, acs_period="2019–2023")
    pv = build(ctx(neighborhood=NeighborhoodSummary(demographics=dm)))
    inc = pv["area.community_area.median_household_income"]
    assert inc["tier"] == "our_calculation" and inc["method_key"] == "bracket_median" and inc["basis_tier"] == "official_estimate"
    assert inc["confidence"] == "low" and inc["confidence_reasons"] == ["bracket_median", "old_source"]  # 2019–2023 is 3 years old
    assert inc["as_of"] == "2023-12-31" and "No margin of error" in inc["note"]
    assert pv["area.community_area.population"]["tier"] == "official_estimate"


# --- building facts, dated by the dataset that supplied them -------------------------------------------

def prop(**kw) -> PropertySummary:
    return PropertySummary(pin14="14313320180000", **kw)


def test_the_2015_footprints_and_the_valuation_year_are_dated():
    p = prop(stories=2.0, stories_source="footprint", year_built=1920, year_built_source="commercial_valuation",
             commercial_valuation_year=2024, bldg_sqft=15647, bldg_sqft_source="commercial_valuation")
    pv = build(ctx(property=p))
    assert (pv["property.stories"]["as_of"], pv["property.stories"]["as_of_basis"]) == ("2015-08-15", "vintage")
    assert pv["property.stories"]["confidence_reasons"] == ["old_source"] and pv["property.stories"]["source_id"] == "chi.building_footprints"
    y = pv["property.year_built"]
    assert (y["as_of"], y["as_of_basis"], y["period"], y["source_id"]) == ("2024-12-31", "tax_year", "2024", "cook.assessor.commercial_valuation")
    assert pv["property.bldg_sqft"]["as_of"] == "2024-12-31"  # the existing area entry gains its vintage


def test_energy_is_dated_by_its_report_year_and_says_owner_reported():
    en = EnergyBenchmark(chicago_energy_rating=3.0, data_year=2023)
    pv = build(ctx(property=prop(energy=en)))
    e = pv["property.energy"]
    assert (e["as_of"], e["period"], e["as_of_basis"]) == ("2023-12-31", "2023", "period_end") and "Owner-reported" in e["note"]


def test_an_assessment_year_still_in_progress_has_no_end_date_yet():
    hist = [AssessmentRecord(year=2026, total=398120.0), AssessmentRecord(year=2025, total=398120.0)]
    pv = build(ctx(property=prop(total_assessed_value=398120.0, assessment_history=hist)))
    av = pv["property.assessed_value"]
    assert av["as_of"] is None and av["as_of_basis"] == "tax_year" and av["period"] == "2026" and "age_days" not in av
    assert year_end(2024, QD) == "2024-12-31" and year_end(2026, QD) is None and year_end("x", QD) is None


# --- tax ------------------------------------------------------------------------------------------------

def test_a_ptaxsim_bill_is_a_government_model_and_a_fallback_is_our_arithmetic():
    ok = build(ctx(property=prop(estimated_annual_tax=82586.11, tax_year=2024, total_assessed_value=398120.0)))
    assert ok["property.tax_estimate"]["tier"] == "official_estimate" and ok["property.tax_estimate"]["period"] == "2024"
    fb = build(ctx(property=prop(estimated_annual_tax=9000.0, tax_year=2024, tax_estimate_is_fallback=True)))
    e = fb["property.tax_estimate"]
    assert e["tier"] == "our_calculation" and e["method_key"] == "calculation" and e["basis_tier"] == "official_record"


def test_the_effective_rate_is_never_stronger_than_its_inputs():
    p = prop(estimated_annual_tax=82586.11, tax_year=2024, total_assessed_value=398120.0, assessment_level=0.25,
             implied_market_value=1592480.0, effective_tax_rate=0.0519)
    pv = build(ctx(property=p))
    e = pv["property.effective_rate"]
    assert e["tier"] == "our_calculation" and e["inputs"] == ["property.tax_estimate", "property.implied_market_value"]
    assert e["basis_tier"] == "official_estimate"  # the PTAXSIM bill is the weakest input


def test_the_class_norm_states_the_tax_year_its_constant_came_from():
    pv = build(ctx(property=prop(assessment_level=0.25, effective_tax_rate=0.05, estimated_annual_tax=1.0)))
    n = pv["property.tax_class_norm"]
    assert n["value"] == round(CLASS_NORM_RATE_PER_LEVEL * 0.25, 4) == 0.0525
    assert (n["period"], n["as_of"]) == (f"tax year {CLASS_NORM_TAX_YEAR}", "2023-12-31")
    assert n["method_params"] == {"rate_per_assessment_level": 0.21, "tax_year": 2023} and "0.2009" in n["note"]
    assert "old_source" in n["confidence_reasons"]


def test_the_backend_class_norm_equals_the_frontends():
    tsx = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "ScorecardPage.tsx").read_text()
    m = re.search(r"EFF_RATE_PER_ASSESSMENT_LEVEL\s*=\s*([0-9.]+)", tsx)
    assert m and float(m.group(1)) == CLASS_NORM_RATE_PER_LEVEL


# --- comps ------------------------------------------------------------------------------------------------

def comp(**kw) -> ComparableSale:
    return ComparableSale(**{"pin": "1", "sale_price": 500000.0, "price_per_land_sqft": 100.0, **kw})


def test_comp_medians_carry_n_and_the_search_basis_actually_used():
    comps = ComparablesSummary(
        median_sale_price=500000.0, median_price_per_land_sqft=100.0, sales_volume=4,
        comp_basis="Class 2xx sales within 0.5 mi, last 5 yr (n=4)", comp_radius_mi=0.5, comp_window_years=5, comp_widened=True,
        sales=[comp(), comp(), comp(), comp(price_per_land_sqft=None)],
    )
    pv = build(ctx(), comparables=comps)
    price, psf = pv["property.comps.median_price"], pv["property.comps.median_price_per_land_sqft"]
    assert price["coverage"] == {"n": 4, "unit": "sales", "sample": "comps"} and psf["coverage"]["n"] == 3
    assert price["method_params"] == {"radius_mi": 0.5, "window_years": 5, "widened": True}
    assert price["period"] == "last 5 years" and "widened past" in price["note"]
    assert price["confidence"] == "low" and price["confidence_reasons"] == ["small_sample"]  # n=4 < 5 fades
    assert psf["confidence"] == "low"  # n=3 also fades
    assert "property.comps.median_price_per_bldg_sqft" not in pv  # no such median: no entry


def test_two_comps_are_withheld_and_the_list_is_not():
    comps = ComparablesSummary(median_sale_price=1.0, sales_volume=2, sales=[comp(), comp()])
    assert build(ctx(), comparables=comps)["property.comps.median_price"]["confidence"] == "withheld"


def test_the_comp_search_records_its_tier(monkeypatch):
    import asyncio

    from backend.retrieval.property import sales

    calls = []

    async def fake(lat, lon, cls, yrs, rad, limit, client):
        calls.append((yrs, rad))
        return {"summary": {}, "sales": [{"pin": "1"}] if len(calls) == 2 else []}

    monkeypatch.setattr(sales, "_query_comps", fake)
    sales._comps_cache.clear() if hasattr(sales._comps_cache, "clear") else None
    out = asyncio.run(sales.nearby_comparable_sales(41.9, -87.6, "2"))
    s = out["summary"]
    assert s["comp_widened"] is True and s["comp_window_years"] == calls[1][0]
    assert s["comp_radius_mi"] == sales._deg_to_mi(calls[1][1]) and calls[1][1] == 2 * calls[0][1]


# --- violations, 311 and the area feeds --------------------------------------------------------------------------

def test_profile_violations_are_address_scoped_and_chat_violations_are_area_scoped():
    v = ViolationSummary(total=20, open_count=3, top_descriptions=[], by_category={"Fire": 2})
    profile = build(ctx(violations=v), address_scoped_violations=True)
    assert "property.violations" in profile and "area.violations" not in profile
    chat = build(ctx(violations=v))
    assert "area.violations" in chat and "property.violations" not in chat and "area.violations.categories" in chat
    both = build(ctx(violations=v, address_violations=AddressViolations(status="present", summary=v)))
    assert "property.violations" in both


def test_the_crime_feed_keeps_its_lag_note_and_cutoff():
    c = ctx(crime_last_90d=CrimeSummary(total=1755, arrest_rate=0.09, by_type={}), community_area_name="West Town",
            data_lag_cutoff="2026-10-14", data_lag_note="Crime data excludes the most recent 7 days (as of 2026-10-14).")
    e = build(c)["area.crime"]
    assert (e["as_of"], e["as_of_basis"], e["period"], e["scope"], e["geography"]) == ("2026-10-14", "period_end", "last 90 days", "community_area", "West Town")
    assert "excludes the most recent 7 days" in e["note"]


def test_a_parcel_less_context_still_gets_its_area_entries():
    c = ContextObject(community_area_name="West Town", crime_last_90d=CrimeSummary(total=5, arrest_rate=0.1, by_type={}))
    pv = build_provenance(context=c, zone_definition=None, resolved_pin=None, resolved_confidence=None, query_date=QD)
    assert "area.crime" in pv and "geo.community_area" in pv


def test_a_negative_result_is_not_a_figure():
    pv = build(ctx(incentives=IncentivesSummary(), regulatory=RegulatorySummary(), property=prop(flags=ParcelFlags())))
    assert not [k for k in pv if k.startswith(("incentive.", "property.flags.", "regulatory."))]


# --- source dates ------------------------------------------------------------------------------------------------

def write_store(path, rows: dict[str, tuple[str, str, str]]):
    now = datetime(2026, 10, 21, 5, 37, tzinfo=timezone.utc)
    with Store(path) as s:
        for sid, (state, as_of, basis) in rows.items():
            s.record(source_id=sid, state=state, reason="", severity="standard", as_of=as_of, basis=basis, age_days=3, now=now,
                     probe_error=False, latency_ms=1, requests=1, prev=None, alerted_state=None, alerted_at=None)
        rid = s.start_run(now)
        s.finish_run(rid, now + timedelta(minutes=1), sources=len(rows), alarms=0, requests=1)
        s.commit()


def test_a_source_date_comes_from_the_data_health_store(tmp_path, monkeypatch):
    db = tmp_path / "h.db"
    write_store(db, {"cook.assessor.sales": ("ok", "2026-09-30", "content"), "chi.crime": ("ok", "2026-10-14", "published")})
    monkeypatch.setattr(status, "DB_FILE", db)
    status.reset_cache()
    assert source_dates("cook.assessor.sales", QD) == {"as_of": "2026-09-30", "as_of_basis": "period_end"}
    assert source_dates("chi.crime", QD) == {"as_of": "2026-10-14", "as_of_basis": "source_updated"}
    sales = build(ctx(property=prop(sales_history=[__import__("backend.models", fromlist=["SaleRecord"]).SaleRecord(date="2024-01-02T00:00:00.000", price=1.0)])))
    e = sales["property.sales"]
    assert e["as_of"] == "2026-09-30" and e["effective_date"] == "2024-01-02"  # the dataset's age, not the sale's


def test_an_unknown_state_row_gives_no_date_and_the_query_date_is_never_an_as_of(tmp_path, monkeypatch):
    db = tmp_path / "h.db"
    write_store(db, {"chi.crime": ("unknown", "2026-10-14", "content")})
    monkeypatch.setattr(status, "DB_FILE", db)
    status.reset_cache()
    d = source_dates("chi.crime", QD)
    assert d["as_of"] is None and d["as_of_basis"] == "queried"


def test_an_unreadable_store_falls_through(tmp_path, monkeypatch):
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    monkeypatch.setattr(status, "DB_FILE", bad)
    status.reset_cache()
    assert status.latest("chi.crime") is None
    assert source_dates("chi.building_footprints", QD)["as_of"] == "2015-08-15"  # the registry's frozen vintage


def test_a_year_only_frozen_vintage_reads_as_that_years_end():
    d = source_dates("artifact.chrs", QD)
    assert (d["as_of"], d["as_of_basis"], d["period"]) == ("1996-12-31", "vintage", "1996")


# --- area benchmark ------------------------------------------------------------------------------------------------

def test_the_area_benchmark_carries_its_sample_coverage_and_index_date():
    stats = {"community_area": 3, "median_mv_per_land_sqft": 187.5, "n_mv_psf": 189, "coverage_share": 189 / 4905, "index_built": "2026-10-01"}
    e = area_benchmark_entry(stats, QD)
    assert e["coverage"]["n"] == 189 and e["coverage"]["sample"] == "area_sample"
    assert e["confidence"] == "withheld" and e["confidence_reasons"] == ["low_coverage"]  # 3.9% of Uptown's parcels
    assert (e["as_of"], e["tier"], e["method_key"], e["basis_tier"]) == ("2026-10-01", "our_calculation", "calculation", "official_record")
    ok = area_benchmark_entry({**stats, "n_mv_psf": 3000, "coverage_share": 0.6}, QD)
    assert ok["confidence"] == "standard"
    assert area_benchmark_entry({"median_mv_per_land_sqft": None, "n_mv_psf": 0}, QD) is None


def test_the_area_scan_reports_coverage_and_the_index_build_date(tmp_path):
    from backend.retrieval import area_stats

    db = tmp_path / "idx.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE parcels (attrs TEXT, regions TEXT)")
    con.execute("CREATE TABLE meta (id INTEGER, built_at INTEGER)")
    con.execute("INSERT INTO meta VALUES (1, ?)", (int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()),))
    rows = [({"total_assessed_value": 100000, "land_sqft": 5000, "class": "205"}, ["neighborhood:24"]),
            ({"total_assessed_value": 120000, "class": "205"}, ["neighborhood:24"])]  # no land area
    for a, r in rows:
        con.execute("INSERT INTO parcels VALUES (?, ?)", (json.dumps(a), json.dumps(r)))
    con.commit()
    con.close()
    stats = area_stats._scan_index(str(db))[24]
    assert stats["n_parcels"] == 2 and stats["n_mv_psf"] == 1 and stats["coverage_share"] == 0.5 and stats["index_built"] == "2026-10-01"


def test_a_zero_is_a_figure():
    """An exempt parcel's $0 assessed value and a tract's 0% vacancy are shown, so they carry entries."""
    pv = build(ctx(property=prop(total_assessed_value=0.0, tax_exempt=True),
                   neighborhood=NeighborhoodSummary(census_tract=tract(vacancy_rate=0.0, moe={}, cv={}))))
    assert pv["property.assessed_value"]["value"] == 0.0 and pv["area.tract.vacancy_rate"]["value"] == 0.0
