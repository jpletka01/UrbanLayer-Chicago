"""Provenance entries for every figure the Property Profile shows, and every area feed a
chat turn can carry (WS0 M3; guide §8). Called by ``provenance.build_provenance``.

One rule: a figure that is not present gets no entry, never a made-up one. A negative result
(not in a TIF district, no flags) is not a figure either, so it gets none. Source-level dates
come from :func:`provenance.resolve_as_of` (the response's own date first, then the data-health
store, then the registry's frozen vintage); the query date is never an as-of.

The capture lives in the retrieval models (ACS margins of error, comp basis, valuation year,
index build date); this module only reads it.
"""

from __future__ import annotations

from typing import Any

from backend.provenance import FACTS, _ISO, _scalar, make_entry, resolve_as_of, weakest_tier
from backend.retrieval.property.assessment_level import CLASS_NORM_NOTE, CLASS_NORM_RATE_PER_LEVEL, CLASS_NORM_TAX_YEAR

# The dataset behind each source code on PropertySummary (land/building area, year, stories, units).
SOURCE_IDS = {
    "assessor": "cook.assessor.characteristics",
    "gis": "cook.gis.parcels",
    "geometry": "cook.ptaxsim",
    "condo_unit": "cook.assessor.condo_characteristics",
    "commercial_valuation": "cook.assessor.commercial_valuation",
    "footprint": "chi.building_footprints",
    "energy_benchmark": "chi.energy_benchmarking",
}


def year_end(year: int | str | None, qd: str) -> str | None:
    """``YYYY-12-31`` for a data year, or None while that date hasn't passed (a year in progress
    has no end date yet, and a negative age would be nonsense)."""
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return None
    d = f"{y}-12-31"
    return d if d < qd else None


def source_dates(source_id: str | None, qd: str) -> dict[str, Any]:
    """``as_of``, ``as_of_basis`` and (for a year-only vintage) ``period`` for a source, by the
    guide's precedence. A frozen source dated by year ("1996") reads as that year's end."""
    as_of, basis = resolve_as_of(source_id)
    out: dict[str, Any] = {"as_of": as_of, "as_of_basis": basis}
    if as_of is None and source_id:
        from backend.data_health.registry import BY_ID

        spec = BY_ID.get(source_id)
        frozen = spec.frozen.as_of if spec and spec.frozen else None
        if frozen and not _ISO.match(frozen) and frozen.isdigit() and len(frozen) == 4:
            out.update(as_of=f"{frozen}-12-31", as_of_basis="vintage", period=frozen)
    return out


def _weakest(out: dict[str, dict], refs: list[str]) -> str | None:
    tiers = [(out[r].get("basis_tier") or out[r]["tier"]) for r in refs if r in out]
    return weakest_tier(tiers)


def _inputs(out: dict[str, dict], refs: list[str]) -> dict[str, Any]:
    have = [r for r in refs if r in out]
    return {"inputs": have, "basis_tier": _weakest(out, have)} if have else {}


def _period_end(period: str | None, qd: str) -> str | None:
    """The end year of "2020–2024" (an ACS release) as a year-end date."""
    if not period:
        return None
    return year_end(period.replace("-", "–").split("–")[-1], qd)


def _money(v: Any) -> int | float | None:
    return v if isinstance(v, (int, float)) else None


def figure_entries(
    context, *, comparables, qd: str, existing: dict[str, dict], address_scoped_violations: bool = False,
) -> dict[str, dict]:
    """Entries for every figure present in ``context`` (+ ``comparables``), not already in ``existing``."""
    out: dict[str, dict] = dict(existing)

    def put(fact: str, value: Any, *, source_id: str | None = None, dates: dict | None = None, **kw) -> None:
        if fact in existing:
            return
        sid = source_id or FACTS[fact].source_id
        d = dates if dates is not None else source_dates(sid, qd)
        kw = {**d, **kw}
        out[fact] = make_entry(fact, query_date=qd, source_id=sid, value=_scalar(value), **kw)

    prop = getattr(context, "property", None)
    zoning = getattr(context, "parcel_zoning", None)
    reg = getattr(context, "regulatory", None)
    inc = getattr(context, "incentives", None)
    hood = getattr(context, "neighborhood", None)
    ca_name = getattr(context, "community_area_name", None)

    # --- the parcel: value, tax, sales, building ----------------------------------------------
    if prop is not None:
        _property_figures(prop, put, out, qd)
    if zoning is not None and prop is not None:
        _zoning_calculations(context, prop, put, out)
    if prop is not None and getattr(prop, "flags", None) is not None:
        _flags(prop.flags, put, qd)

    # --- violations and 311: address- or area-scoped ----------------------------------------------
    av = getattr(context, "address_violations", None)
    addr_viol = getattr(av, "summary", None) if av else None
    if addr_viol is None and address_scoped_violations:
        addr_viol = getattr(context, "violations", None)
    area_viol = None if address_scoped_violations else getattr(context, "violations", None)
    if addr_viol is not None:
        put("property.violations", addr_viol.total, geography=getattr(context, "resolved_address", None),
            note=f"{addr_viol.open_count} open." if getattr(addr_viol, "open_count", None) is not None else None)
    a311 = getattr(context, "address_311", None)
    if a311 is not None:
        put("property.311", a311.total, geography=getattr(context, "resolved_address", None), period="past year",
            note=f"{a311.open_count} open." if a311.open_count is not None else None)

    # --- regulatory ---------------------------------------------------------------------------------
    if reg is not None:
        if reg.flood_zone:
            put("regulatory.flood", reg.flood_zone,
                note="In a special flood hazard area." if reg.in_special_flood_hazard else None)
        if reg.brownfield_sites:
            put("regulatory.environmental", len(reg.brownfield_sites), note="EPA-registered facilities near the parcel.")

    # --- incentives ---------------------------------------------------------------------------------
    if inc is not None:
        _incentives(inc, reg, put)

    # --- neighborhood -------------------------------------------------------------------------------
    cn = getattr(context, "community_area", None)
    if ca_name:
        put("geo.community_area", ca_name, geography=ca_name, record_id=str(cn) if cn else None)
    if hood is not None:
        _neighborhood(hood, put, qd, ca_name)

    # --- area feeds (every ContextObject, chat included) --------------------------------------------
    _area_feeds(context, put, address_scoped_violations, area_viol, ca_name)

    # --- comparable sales -----------------------------------------------------------------------------
    comps = comparables if comparables is not None else getattr(context, "comparables", None)
    if comps is not None:
        _comps(comps, put, qd)

    return {k: v for k, v in out.items() if k not in existing}


# --- parcel ----------------------------------------------------------------------------------------

def _building_dates(src: str | None, prop, qd: str) -> dict[str, Any]:
    """Dates for a building fact by the dataset that supplied it: the footprints' frozen vintage,
    the commercial valuation's assessment year, the energy report's data year."""
    sid = SOURCE_IDS.get(src or "")
    if src == "commercial_valuation" and getattr(prop, "commercial_valuation_year", None):
        y = prop.commercial_valuation_year
        return {"as_of": year_end(y, qd), "as_of_basis": "tax_year", "period": str(y)}
    if src == "energy_benchmark" and getattr(getattr(prop, "energy", None), "data_year", None):
        y = prop.energy.data_year
        return {"as_of": year_end(y, qd), "as_of_basis": "period_end", "period": str(y)}
    return source_dates(sid, qd)


def _property_figures(prop, put, out: dict[str, dict], qd: str) -> None:
    hist = [r for r in (prop.assessment_history or []) if getattr(r, "year", None)]
    latest = max(hist, key=lambda r: r.year) if hist else None
    if prop.total_assessed_value is not None:
        yr = latest.year if latest else None
        put("property.assessed_value", prop.total_assessed_value, record_id=prop.pin14,
            dates={"as_of": year_end(yr, qd), "as_of_basis": "tax_year", **({"period": str(yr)} if yr else {})},
            note=f"Assessment year {yr}." if yr else None)
    if hist:
        put("property.assessment_history", len(hist), record_id=prop.pin14,
            period=f"{min(r.year for r in hist)}–{max(r.year for r in hist)}",
            dates=source_dates("cook.assessor.values", qd))
    if prop.implied_market_value is not None and prop.assessment_level:
        put("property.implied_market_value", prop.implied_market_value,
            note=f"Assessed value divided by the class's {prop.assessment_level:.0%} assessment level.",
            **_inputs(out, ["property.assessed_value"]) or {"inputs": ["cook.assessor.values"]})
    if prop.estimated_annual_tax is not None:
        ty = prop.tax_year
        dates = {"as_of": year_end(ty, qd), "as_of_basis": "tax_year", **({"period": str(ty)} if ty else {})}
        if prop.tax_estimate_is_fallback:
            put("property.tax_estimate", prop.estimated_annual_tax, tier="our_calculation", method_key="calculation",
                dates=dates, inputs=["cook.assessor.values"],
                note="No PTAXSIM bill for this parcel: estimated from the assessed value at a typical effective rate.")
        else:
            put("property.tax_estimate", prop.estimated_annual_tax, dates=dates, record_id=prop.pin14,
                note=f"Tax year {ty} bill computed by PTAXSIM." if ty else None)
    if prop.effective_tax_rate is not None:
        put("property.effective_rate", prop.effective_tax_rate,
            dates={"as_of": year_end(prop.tax_year, qd), "as_of_basis": "tax_year",
                   **({"period": str(prop.tax_year)} if prop.tax_year else {})},
            **_inputs(out, ["property.tax_estimate", "property.implied_market_value"]),
            note="Annual tax divided by implied market value.")
    if prop.assessment_level:
        put("property.tax_class_norm", round(CLASS_NORM_RATE_PER_LEVEL * prop.assessment_level, 4),
            dates={"as_of": year_end(CLASS_NORM_TAX_YEAR, qd), "as_of_basis": "tax_year", "period": f"tax year {CLASS_NORM_TAX_YEAR}"},
            method_params={"rate_per_assessment_level": CLASS_NORM_RATE_PER_LEVEL, "tax_year": CLASS_NORM_TAX_YEAR},
            inputs=["cook.ptaxsim"], note=CLASS_NORM_NOTE)
    if prop.tax_exemptions:
        put("property.exemptions", len(prop.tax_exemptions),
            dates={"as_of": year_end(prop.tax_year, qd), "as_of_basis": "tax_year",
                   **({"period": str(prop.tax_year)} if prop.tax_year else {})},
            note=", ".join(sorted({e.kind for e in prop.tax_exemptions})))
    if prop.sales_history:
        newest = max((s.date or "")[:10] for s in prop.sales_history)
        put("property.sales", len(prop.sales_history), record_id=prop.pin14,
            effective_date=newest if _ISO.match(newest) else None, note="Count of recorded sales; dates are the sale dates.")
    appeals = getattr(prop, "appeals", None)
    if appeals and appeals.records:
        years = sorted({r.year for r in appeals.records if r.year})
        put("property.appeals", len(appeals.records), record_id=prop.pin14,
            period=f"{years[0]}–{years[-1]}" if years else None, dates=source_dates("cook.assessor.appeals", qd))
    ap = getattr(prop, "assessor_permits", None)
    if ap and ap.count:
        put("property.assessor_permits", ap.count, record_id=prop.pin14,
            effective_date=ap.latest_date[:10] if ap.latest_date and _ISO.match(ap.latest_date[:10]) else None,
            note="Assessable and unclosed: a future assessment change." if ap.assessable_pending else None)

    # building facts, each by the dataset that supplied it
    if prop.year_built:
        sid = SOURCE_IDS.get(prop.year_built_source or "", "cook.assessor.characteristics")
        put("property.year_built", prop.year_built, source_id=sid, record_id=prop.pin14,
            dates=_building_dates(prop.year_built_source, prop, qd))
    if prop.stories:
        sid = SOURCE_IDS.get(prop.stories_source or "", "cook.assessor.characteristics")
        put("property.stories", prop.stories, source_id=sid, record_id=prop.pin14,
            dates=_building_dates(prop.stories_source, prop, qd))
    if prop.units:
        sid = SOURCE_IDS.get(prop.units_source or "", "cook.assessor.characteristics")
        put("property.units", prop.units, source_id=sid, record_id=prop.pin14,
            dates=_building_dates(prop.units_source, prop, qd))
    en = getattr(prop, "energy", None)
    if en is not None and (en.chicago_energy_rating is not None or en.energy_star_score is not None or en.site_eui is not None):
        value = en.chicago_energy_rating if en.chicago_energy_rating is not None else en.energy_star_score
        put("property.energy", value, record_id=prop.pin14,
            dates={"as_of": year_end(en.data_year, qd), "as_of_basis": "period_end",
                   **({"period": str(en.data_year)} if en.data_year else {})},
            note="Owner-reported to the City's benchmarking program.")
    if prop.bldg_sqft and prop.land_sqft:
        put("property.far_used", round(prop.bldg_sqft / prop.land_sqft, 2),
            **_inputs(out, ["property.bldg_sqft", "property.land_sqft"]),
            note="Building area divided by lot area.")


def _zoning_calculations(context, prop, put, out: dict[str, dict]) -> None:
    uy = getattr(context, "unit_yield", None)
    if uy and uy.get("units") is not None:
        put("zoning.unit_yield", uy["units"],
            **_inputs(out, ["property.land_sqft", "zoning.min_lot_area_per_unit"]),
            note="By lot area only; other standards can bind first.")
    adu = getattr(context, "adu", None)
    if adu and adu.get("status"):
        put("zoning.adu", adu["status"],
            **_inputs(out, ["zoning.district", "overlay.adu_area", "code.vintage"]))
    tod = getattr(context, "tod_benefits", None)
    if tod:
        put("zoning.tod_benefits", tod.get("parking_max_reduction_pct") if tod.get("parking_relief") else "none",
            **_inputs(out, ["zoning.district", "overlay.tod_cta", "overlay.tod_metra", "code.vintage"]))


def _flags(flags, put, qd: str) -> None:
    if flags.chrs_rating:
        put("property.flags.chrs", flags.chrs_rating, label=f"Historic Resources Survey rating ({flags.chrs_rating})",
            note="Frozen 1996 survey; an orange or red rating holds a demolition permit up to 90 days.")
    years = sorted(set(flags.tax_sale_years) | set(flags.scavenger_sale_years))
    if years:
        put("property.flags.tax_sale", ", ".join(str(y) for y in years),
            note="Historic: the public tax-sale datasets end in 2014-2016.")
    if flags.city_owned:
        put("property.flags.city_owned", True, note=flags.city_owned_status)
    if flags.scofflaw:
        put("property.flags.scofflaw", True, record_id=flags.scofflaw_case)
    if flags.str_prohibited:
        put("property.flags.str_prohibited", True)


def _incentives(inc, reg, put) -> None:
    if inc.in_tif_district and inc.tif_name:
        years = [r.get("year") for r in (inc.tif_fund_history or []) if isinstance(r, dict) and r.get("year")]
        put("incentive.tif", inc.tif_name, geography=inc.tif_name,
            **({"period": str(max(years)), "note": "Period is the latest TIF annual report year."} if years else {}))
    if inc.in_enterprise_zone:
        put("incentive.enterprise_zone", inc.enterprise_zone_name or True, geography=inc.enterprise_zone_name)
    if inc.in_opportunity_zone:
        put("incentive.opportunity_zone", inc.oz_tract or True, geography=inc.oz_tract)
    if inc.in_qct:
        put("incentive.lihtc", inc.qct_tract or True, geography=inc.qct_tract)
    if inc.in_nmtc:
        put("incentive.nmtc", inc.nmtc_tract or True, geography=inc.nmtc_tract,
            note="Severely distressed." if inc.nmtc_severe_distress else None)
    gp = inc.grant_programs
    if gp is not None and gp.total_projects:
        put("incentive.grants", gp.total_projects, note=f"{gp.total_projects} projects across {len(gp.by_program)} programs.")
    aro = getattr(reg, "aro_housing", None) if reg is not None else None
    if aro is not None and aro.total_projects:
        put("incentive.aro", aro.total_projects, note=f"{aro.total_units} units.")


# --- neighborhood ------------------------------------------------------------------------------------

def _neighborhood(hood, put, qd: str, ca_name: str | None) -> None:
    if hood.ward is not None:
        put("neighborhood.ward", hood.ward.ward, geography=f"Ward {hood.ward.ward}",
            note=f"Alderman {hood.ward.alderman}." if hood.ward.alderman else None)
    t = hood.transit
    if t is not None and (t.nearest_cta_rail or t.nearest_metra):
        put("neighborhood.transit", t.nearest_cta_rail or t.nearest_metra,
            note=(f"{t.cta_rail_distance_mi} mi to the nearest CTA rail station." if t.nearest_cta_rail and t.cta_rail_distance_mi is not None else None))
    d = hood.divvy
    if d is not None and d.nearest_station:
        put("neighborhood.divvy", d.nearest_station, note=f"{d.distance_mi} mi; {d.stations_within_radius} stations within {d.radius_mi} mi.")
    tr = hood.traffic
    if tr is not None and tr.daily_vehicles is not None:
        put("neighborhood.traffic", tr.daily_vehicles, geography=tr.road,
            dates={"as_of": tr.as_of if tr.as_of and _ISO.match(tr.as_of) else None,
                   "as_of_basis": "period_end" if tr.as_of else "queried", "period": "7-day average"},
            note="Both directions of the nearest counted street.")
    w = hood.walkscore
    if w is not None and w.walk_score is not None:
        put("neighborhood.walkscore", w.walk_score, url=w.ws_link, note="Walk Score is a private company's index.")

    ct = hood.census_tract
    if ct is not None:
        end = _period_end(ct.acs_period, qd)
        for field in _TRACT_ORDER:
            val = getattr(ct, field, None)
            if val is None:
                continue
            moe = ct.moe.get(field)
            precision = (
                {"moe": moe, "moe_level": 0.9, **({"cv": ct.cv[field]} if field in ct.cv else {})}
                if moe is not None else None
            )
            scope = "city" if field == "city_median_income" else "county" if field == "county_median_income" else "tract"
            geography = {"city": "Chicago", "county": "Cook County"}.get(scope, ct.tract_name)
            put(f"area.tract.{field}", val, geography=geography, period=ct.acs_period,
                dates={"as_of": end, "as_of_basis": "period_end"},
                url=ct.census_reporter_url, precision=precision,
                note=f"ACS {ct.acs_period} 5-year{f' ({ct.acs_release})' if ct.acs_release else ''}"
                     f"{'; margin of error is in percentage points' if field.endswith(('_pct', '_rate')) else ''}.")
    dm = hood.demographics
    if dm is not None:
        end = _period_end(dm.acs_period, qd)
        if dm.population is not None:
            put("area.community_area.population", dm.population, geography=dm.community_area_name or ca_name,
                period=dm.acs_period, dates={"as_of": end, "as_of_basis": "period_end"})
        if dm.median_household_income is not None:
            put("area.community_area.median_household_income", dm.median_household_income,
                geography=dm.community_area_name or ca_name, period=dm.acs_period,
                dates={"as_of": end, "as_of_basis": "period_end"},
                inputs=["chi.acs_community_area"],
                note="Interpolated from five income brackets; the top bracket is capped. No margin of error is published.")


_TRACT_ORDER = (
    "population", "median_household_income", "per_capita_income", "median_home_value", "median_gross_rent",
    "owner_occupied_pct", "vacancy_rate", "poverty_rate", "unemployment_rate", "bachelors_or_higher_pct",
    "foreign_born_pct", "city_median_income", "county_median_income",
)


def _area_feeds(context, put, address_scoped_violations: bool, area_viol, ca_name: str | None) -> None:
    geo = ca_name
    crime = getattr(context, "crime_last_90d", None)
    if crime is not None:
        cutoff = getattr(context, "data_lag_cutoff", None)
        put("area.crime", crime.total, geography=geo, period="last 90 days",
            dates={"as_of": cutoff if cutoff and _ISO.match(cutoff) else None,
                   "as_of_basis": "period_end" if cutoff else "queried"},
            note=" ".join(x for x in (getattr(context, "data_lag_note", None),
                                      "Counts are a floor: the query hit its row cap." if crime.capped else None) if x) or None)
    o311 = getattr(context, "open_311_requests", None)
    if o311 is not None:
        put("area.311", o311.total, geography=geo, note="Open requests." + (" Counts are a floor: the query hit its row cap." if o311.capped else ""))
    permits = getattr(context, "permits", None)
    if permits is not None:
        put("area.permits", permits.total, geography=geo,
            note="Counts are a floor: the query hit its row cap." if permits.capped else None)
    if area_viol is not None:
        put("area.violations", area_viol.total, geography=geo,
            note="Counts are a floor: the query hit its row cap." if area_viol.capped else None)
        if area_viol.by_category:
            put("area.violations.categories", len(area_viol.by_category), geography=geo,
                inputs=["chi.violations"], note="Our keyword grouping of free-text violation descriptions.")
    biz = getattr(context, "businesses", None)
    if biz is not None:
        put("area.business", biz.total, geography=geo,
            note="Counts are a floor: the query hit its row cap." if biz.capped else None)
    vac = getattr(context, "vacant_buildings", None)
    if vac is not None:
        put("area.vacant", vac.total, geography=geo)
    food = getattr(context, "food_inspections", None)
    if food is not None:
        put("area.food", food.total, geography=geo)


# --- comparable sales ----------------------------------------------------------------------------------

def _comps(comps, put, qd: str) -> None:
    sales = list(getattr(comps, "sales", None) or [])
    if not sales:
        return
    radius, years, widened = comps.comp_radius_mi, comps.comp_window_years, bool(comps.comp_widened)
    basis = comps.comp_basis
    params = {k: v for k, v in (("radius_mi", radius), ("window_years", years), ("widened", widened)) if v is not None}
    note = basis or None
    if widened:
        note = f"The search widened past ¼ mile and 3 years. {basis or ''}".strip()
    metrics = (
        ("property.comps.median_price", comps.median_sale_price, lambda s: s.sale_price),
        ("property.comps.median_price_per_land_sqft", comps.median_price_per_land_sqft, lambda s: s.price_per_land_sqft),
        ("property.comps.median_price_per_bldg_sqft", comps.median_price_per_bldg_sqft, lambda s: s.price_per_bldg_sqft),
        ("property.comps.median_price_per_buildable_sqft", comps.median_price_per_buildable_sqft, lambda s: s.price_per_buildable_sqft),
    )
    for fact, value, getter in metrics:
        if value is None:
            continue
        n = sum(1 for s in sales if getter(s) is not None)
        if fact.endswith("buildable_sqft") and comps.buildable_median_n:
            n = comps.buildable_median_n
        extra = {"buildable_basis": comps.buildable_median_basis} if fact.endswith("buildable_sqft") and comps.buildable_median_basis else {}
        put(fact, value, geography=basis, period=f"last {years} years" if years else None,
            coverage={"n": n, "unit": "sales", "sample": "comps"},
            method_params={**params, **extra} or None, inputs=["cook.assessor.sales"], note=note)


# --- the declared list: what a Profile payload must carry entries for -----------------------------------

def _get(d: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def _pos(v: Any) -> bool:
    """A positive number: lot and building area, year built, stories and units are absent at 0."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _has(v: Any) -> bool:
    """Present: not missing, not empty, not a False flag. A zero is a figure (0% vacancy)."""
    return not (v is None or v is False or (isinstance(v, (str, list, dict)) and not v))


def expected_fact_ids(payload: dict) -> set[str]:
    """The fact ids a ``/api/scorecard`` payload's figures call for: one per figure present.
    Written from the payload's JSON shape, independent of the builder, so the coverage test
    and ``eval/confidence_audit.py`` catch a figure the builder forgot.

    A figure is "present" when its value is there; a negative result (not in a TIF district,
    no flags, an empty list) is not a figure."""
    from backend.provenance import BULK_SECTIONS, bulk_family

    c = payload.get("context") or {}
    p = lambda path: _get(c, path)  # noqa: E731
    want: set[str] = set()

    def add_if(fact: str, cond: Any) -> None:
        if _has(cond):
            want.add(fact)

    zc = p("parcel_zoning.zone_class")
    add_if("zoning.district", zc)
    POSITIVE = {"property.land_sqft", "property.bldg_sqft", "property.year_built", "property.stories", "property.units"}
    zd = payload.get("zone_definition") or {}
    fam = bulk_family(zc) if zc else None
    if fam and not zd.get("is_fallback"):
        for fact, section in BULK_SECTIONS[fam].items():
            if section is not None and zd.get(fact) not in (None, ""):
                want.add(f"zoning.{fact}")
    for ov in p("regulatory.overlays") or []:
        want.add(f"overlay.{ov['layer_type']}")
    add_if("parcel.identity", payload.get("resolved_pin"))
    add_if("code.vintage", p("code_vintage.current_through"))
    for fact, path in (
        ("property.land_sqft", "property.land_sqft"), ("property.bldg_sqft", "property.bldg_sqft"),
        ("property.assessed_value", "property.total_assessed_value"),
        ("property.assessment_history", "property.assessment_history"),
        ("property.implied_market_value", "property.implied_market_value"),
        ("property.tax_estimate", "property.estimated_annual_tax"),
        ("property.effective_rate", "property.effective_tax_rate"),
        ("property.tax_class_norm", "property.assessment_level"),
        ("property.exemptions", "property.tax_exemptions"),
        ("property.sales", "property.sales_history"),
        ("property.appeals", "property.appeals.records"),
        ("property.assessor_permits", "property.assessor_permits.count"),
        ("property.year_built", "property.year_built"), ("property.stories", "property.stories"),
        ("property.units", "property.units"),
        ("property.flags.chrs", "property.flags.chrs_rating"),
        ("property.flags.city_owned", "property.flags.city_owned"),
        ("property.flags.scofflaw", "property.flags.scofflaw"),
        ("property.flags.str_prohibited", "property.flags.str_prohibited"),
        ("zoning.unit_yield", "unit_yield.units"), ("zoning.adu", "adu.status"), ("zoning.tod_benefits", "tod_benefits"),
        ("regulatory.flood", "regulatory.flood_zone"), ("regulatory.environmental", "regulatory.brownfield_sites"),
        ("geo.community_area", "community_area_name"),
        ("neighborhood.ward", "neighborhood.ward"),
        ("neighborhood.divvy", "neighborhood.divvy.nearest_station"),
        ("neighborhood.traffic", "neighborhood.traffic.daily_vehicles"),
        ("neighborhood.walkscore", "neighborhood.walkscore.walk_score"),
        ("area.community_area.population", "neighborhood.demographics.population"),
        ("area.community_area.median_household_income", "neighborhood.demographics.median_household_income"),
        ("property.311", "address_311"), ("property.violations", "violations"),
        ("area.crime", "crime_last_90d"), ("area.311", "open_311_requests"), ("area.permits", "permits"),
        ("area.business", "businesses"), ("area.vacant", "vacant_buildings"), ("area.food", "food_inspections"),
        ("incentive.tif", "incentives.tif_name"), ("incentive.enterprise_zone", "incentives.in_enterprise_zone"),
        ("incentive.opportunity_zone", "incentives.in_opportunity_zone"), ("incentive.lihtc", "incentives.in_qct"),
        ("incentive.nmtc", "incentives.in_nmtc"), ("incentive.grants", "incentives.grant_programs.total_projects"),
        ("incentive.aro", "regulatory.aro_housing.total_projects"),
    ):
        add_if(fact, _pos(p(path)) if fact in POSITIVE else p(path))
    if p("incentives.in_tif_district") is not True:
        want.discard("incentive.tif")
    if _pos(p("property.bldg_sqft")) and _pos(p("property.land_sqft")):
        want.add("property.far_used")
    en = p("property.energy") or {}
    if any(en.get(k) is not None for k in ("chicago_energy_rating", "energy_star_score", "site_eui")):
        want.add("property.energy")
    flags = p("property.flags") or {}
    if flags.get("tax_sale_years") or flags.get("scavenger_sale_years"):
        want.add("property.flags.tax_sale")
    t = p("neighborhood.transit") or {}
    if t.get("nearest_cta_rail") or t.get("nearest_metra"):
        want.add("neighborhood.transit")
    for field in _TRACT_ORDER:
        add_if(f"area.tract.{field}", p(f"neighborhood.census_tract.{field}") if p(f"neighborhood.census_tract.{field}") is not None else None)
    if (p("violations") or {}).get("by_category"):
        pass  # profile violations are address-scoped; the category grouping is an area-feed fact
    comps = payload.get("comparables") or {}
    if comps.get("sales"):
        for fact, key in (
            ("property.comps.median_price", "median_sale_price"),
            ("property.comps.median_price_per_land_sqft", "median_price_per_land_sqft"),
            ("property.comps.median_price_per_bldg_sqft", "median_price_per_bldg_sqft"),
            ("property.comps.median_price_per_buildable_sqft", "median_price_per_buildable_sqft"),
        ):
            if comps.get(key) is not None:
                want.add(fact)
    return want


def area_benchmark_entry(stats: dict, qd: str | None = None) -> dict | None:
    """The provenance entry for a community area's median market value per land ft², served beside
    it by ``/api/area-stats``: how many of the area's parcels it rests on (the index's land area is
    sparse), and when the index was built. None when there is no median."""
    from datetime import datetime, timezone

    if stats.get("median_mv_per_land_sqft") is None or not stats.get("n_mv_psf"):
        return None
    qd = qd or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    built = stats.get("index_built")
    return make_entry(
        "area.benchmarks.market_value_per_land_sqft", query_date=qd,
        value=_scalar(round(stats["median_mv_per_land_sqft"], 2)),
        as_of=built if built and _ISO.match(built) else None,
        as_of_basis="source_updated" if built else "queried",
        geography=f"Community area {stats.get('community_area')}",
        coverage={"n": stats["n_mv_psf"], "share": stats.get("coverage_share"), "universe": "parcels in the community area",
                  "unit": "parcels", "sample": "area_sample"},
        inputs=["cook.assessor.values", "cook.assessor.characteristics"],
        note="Assessed value divided by the class assessment level, per land ft², across parcels with a land area.",
    )
