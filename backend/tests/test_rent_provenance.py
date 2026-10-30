"""WS4 PR2 slice 2: current official rent in the confidence standard and in chat.

The rules are the existing ones (guide section 3): the coefficient of variation fades a figure above 30% and
withholds it above 50%; an aggregated median with a derived margin uses that rule (``moe_method``), and a median
with no derivable margin stays low (the bracket-median method rule).
"""

from __future__ import annotations


from backend.chat_sources import build_sources_footer
from backend.main import _provenance_for
from backend.models import (
    BedroomRent, CommunityAreaRent, ContextObject, NeighborhoodSummary, RentEvidence,
)
from backend.provenance import _clear_figure, withhold_low_evidence
from backend.provenance_figures import expected_fact_ids
from backend.retrieval.neighborhood import rent as rent_mod
from backend.synthesizer import _build_user_text


def area_rent(community_area: int = 24) -> CommunityAreaRent:
    return rent_mod.community_area_rent(community_area)


def bedroom(group="1_bedroom", scope="tract", est=2000, moe=100.0, fallback=None, geography=None) -> BedroomRent:
    return BedroomRent(bedrooms=group, scope=scope, geography=geography or ("Census Tract 8310, Cook, IL" if scope == "tract" else "West Town PUMA, IL"),
                       geoid="17031831000" if scope == "tract" else "1703159", estimate=est, moe=moe,
                       cv=None if est is None or moe is None else round(moe / 1.645 / est, 3), tract_fallback=fallback)


def ctx_with(rent: RentEvidence) -> ContextObject:
    return ContextObject(community_area=24, community_area_name="West Town", neighborhood=NeighborhoodSummary(rent=rent))


def evidence(**kw) -> RentEvidence:
    base = dict(community_area=area_rent(), acs_period="2020–2024", acs_release="acs2024_5yr",
                bedrooms=[bedroom("1_bedroom"), bedroom("2_bedrooms", est=2400, moe=120.0), bedroom("3_bedrooms", est=3000, moe=300.0)])
    return RentEvidence(**{**base, **kw})


def prov(ctx: ContextObject) -> dict:
    return _provenance_for(ctx)


# --- the entries -------------------------------------------------------------------------------------------


def test_community_area_rent_is_our_calculation_on_a_census_estimate_with_a_derived_margin():
    e = prov(ctx_with(evidence()))["area.rent.community_area"]
    assert e["tier"] == "our_calculation" and e["basis_tier"] == "official_estimate"
    assert e["method_key"] == "bracket_median" and e["source_id"] == "artifact.rent_by_area"
    assert e["scope"] == "community_area" and e["geography"] == "West Town" and e["period"] == "2020–2024"
    assert e["as_of"] == "2024-12-31" and e["as_of_basis"] == "period_end"
    assert e["precision"]["moe_method"] == "acs_handbook_median" and e["precision"]["moe_level"] == 0.9
    assert e["precision"]["moe"] > 0 and e["confidence"] == "standard"
    assert "design factor 1.5" in e["note"]


def test_a_tight_margin_is_standard_and_a_wide_one_fades_or_withholds_by_the_cv_rule():
    states = {a: prov(ctx_with(evidence(community_area=area_rent(a))))["area.rent.community_area"]["confidence"] for a in (24, 37, 47)}
    assert states[24] == "standard"
    assert states[37] == "withheld"  # 727 households: the margin is 160% of the median
    assert states[47] == "withheld"


def test_a_median_with_no_derivable_margin_stays_low():
    ca = area_rent().model_copy(update={"moe": None, "cv": None})
    e = prov(ctx_with(evidence(community_area=ca)))["area.rent.community_area"]
    assert e["confidence"] == "low" and "bracket_median" in e["confidence_reasons"] and "precision" not in e


def test_bedroom_figures_are_the_censuss_own_and_name_their_scope():
    p = prov(ctx_with(evidence(bedrooms=[bedroom("1_bedroom"), bedroom("2_bedrooms", scope="puma", est=2200, moe=90.0, fallback="suppressed")])))
    tract_e, puma_e = p["area.rent.1_bedroom"], p["area.rent.2_bedrooms"]
    assert (tract_e["scope"], tract_e["tier"], tract_e["method_key"]) == ("tract", "official_estimate", "survey_estimate")
    assert (puma_e["scope"], puma_e["geography"]) == ("puma", "West Town PUMA, IL")
    assert "precision" in puma_e and "moe_method" not in puma_e["precision"]  # the Census states this margin
    assert "publishes no median for the parcel's tract" in puma_e["note"]
    assert "area.rent.3_bedrooms" not in p


def test_a_suppressed_cell_is_not_a_figure():
    p = prov(ctx_with(evidence(bedrooms=[bedroom("1_bedroom", est=None, moe=None, fallback="suppressed")])))
    assert "area.rent.1_bedroom" not in p


def test_a_wide_bedroom_margin_withholds_with_the_cv_reason():
    p = prov(ctx_with(evidence(bedrooms=[bedroom("3_bedrooms", est=2000, moe=1800.0)])))
    e = p["area.rent.3_bedrooms"]
    assert e["confidence"] == "withheld" and e["confidence_reasons"] == ["high_cv"]


# --- chat: withheld rent never reaches the model --------------------------------------------------------


def test_withheld_community_area_rent_is_cleared_and_explained():
    ctx = ctx_with(evidence(community_area=area_rent(37)))
    assert '"median": 590' in _build_user_text(ctx, "q")
    withhold_low_evidence(ctx, prov(ctx))
    assert ctx.neighborhood.rent.community_area.median is None and ctx.neighborhood.rent.community_area.moe is None
    (w,) = ctx.withheld_figures
    assert w.fact_id == "area.rent.community_area" and "margin of error" in w.reason
    assert '"median": 590' not in _build_user_text(ctx, "q")


def test_withheld_bedroom_rent_is_cleared_and_the_rest_stays():
    ctx = ctx_with(evidence(bedrooms=[bedroom("1_bedroom"), bedroom("3_bedrooms", est=2000, moe=1800.0)]))
    withhold_low_evidence(ctx, prov(ctx))
    cells = {b.bedrooms: b for b in ctx.neighborhood.rent.bedrooms}
    assert cells["3_bedrooms"].estimate is None and cells["1_bedroom"].estimate == 2000
    assert [w.fact_id for w in ctx.withheld_figures] == ["area.rent.3_bedrooms"]


def test_clearing_rent_never_edits_the_shared_object():
    shared = evidence(community_area=area_rent(37))
    ctx = ctx_with(shared)
    withhold_low_evidence(ctx, prov(ctx))
    assert shared.community_area.median == 590 and ctx.neighborhood.rent is not shared


def test_every_rent_fact_has_a_place_to_be_cleared():
    ctx = ctx_with(evidence(bedrooms=[bedroom("1_bedroom"), bedroom("2_bedrooms", est=2400, moe=120.0), bedroom("3_bedrooms", est=3000, moe=300.0)]))
    for fact in ("area.rent.community_area", "area.rent.1_bedroom", "area.rent.2_bedrooms", "area.rent.3_bedrooms"):
        assert _clear_figure(ctx, fact), fact
    assert not _clear_figure(ContextObject(), "area.rent.1_bedroom")


def test_the_calculated_rent_is_named_for_what_it_is_to_the_model():
    ctx = ctx_with(evidence())
    withhold_low_evidence(ctx, prov(ctx))
    assert any(n.fact_id == "area.rent.community_area" for n in ctx.figure_notes)  # tier D: say it is our aggregation


def test_the_prompt_forbids_a_community_area_rent_by_bedroom():
    from backend.prompts import SYNTHESIZER_SYSTEM

    assert "NO rent by bedroom count for a community area" in SYNTHESIZER_SYSTEM and "PUMA" in SYNTHESIZER_SYSTEM


def test_the_sources_footer_names_the_rent_sources_and_the_derived_margin():
    p = prov(ctx_with(evidence()))
    footer = build_sources_footer(p, [], None)
    assert "Overall rent by community area" in footer and "ACS Handbook method" in footer
    assert "West Town" in footer


# --- the payload contract --------------------------------------------------------------------------------


def test_expected_fact_ids_follow_the_rent_block():
    payload = {"context": {"neighborhood": {"rent": evidence().model_dump(mode="json")}}}
    want = expected_fact_ids(payload)
    assert {"area.rent.community_area", "area.rent.1_bedroom", "area.rent.2_bedrooms", "area.rent.3_bedrooms"} <= want
    payload["context"]["neighborhood"]["rent"]["bedrooms"][0]["estimate"] = None
    assert "area.rent.1_bedroom" not in expected_fact_ids(payload)


def test_the_report_does_not_list_rent_as_a_source_it_used():
    from backend.models import ReportData
    from backend.report_provenance import entries_for_report, sources_rows
    from backend.report_i18n import make_translator

    ctx = ctx_with(evidence())
    report = ReportData(context=ctx, resolved_pin="14313180131001", resolved_confidence="authoritative")
    entries = entries_for_report(report)
    assert not [k for k in entries if k.startswith("area.rent.")]
    assert "artifact.rent_by_area" not in {r["source_id"] for r in sources_rows(entries, make_translator("en"))}
