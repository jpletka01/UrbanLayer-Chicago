"""WS4 PR3: the Assessor's modeled apartment income as its own series.

The artifact is built offline from Commercial Valuation (csik-bsws); the request path only reads it. What these
tests pin: the builder's rules (apartments only, priced buildings only, the median), the committed artifact's
shape, the series' own provenance entry (tier C, a government model, never merged with the ACS rents), the
coverage rules that withhold it (n < 30, under 10%, above 100% = not comparable), and that a withheld figure
never reaches the chat model.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from backend import provenance as P
from backend.chat_sources import build_sources_footer
from backend.data_health import artifacts
from backend.main import _provenance_for
from backend.models import AssessorModelRent, ContextObject, NeighborhoodSummary, RentEvidence
from backend.prompts import SYNTHESIZER_SYSTEM
from backend.provenance import _clear_figure, confidence_state, withhold_low_evidence
from backend.provenance_figures import expected_fact_ids
from backend.retrieval.neighborhood import rent as rent_mod
from backend.retrieval.neighborhood.rent import RentArtifactError
from backend.synthesizer import _build_user_text
from ingestion import build_assessor_model_artifact as build

FACT = "area.rent.assessor_model"


@pytest.fixture(autouse=True)
def _fresh_artifact():
    rent_mod.reset_artifact()
    yield
    rent_mod.reset_artifact()


def row(units=10, pgi=120_000.0, kind="Multifamily-Low Rise (3 floors or less)", pin="14-01-100-001-0000"):
    return {"keypin": pin, "tot_units": str(units), "pgi": None if pgi is None else str(pgi), "property_type_use": kind}


# --- the builder's rules ---------------------------------------------------------------------------------------


def test_summarize_counts_only_apartment_buildings_with_a_modeled_income():
    rows = [
        row(units=10, pgi=120_000, pin="14-01-100-001-0000"),            # $1,000 per unit per month
        row(units=20, pgi=480_000, pin="14-01-100-002-0000"),            # $2,000
        row(units=30, pgi=360_000, pin="14-01-100-003-0000"),            # $1,000
        row(units=300, pgi=None, kind="Hotels-Full Service Luxury", pin="14-01-100-004-0000"),  # rooms, not apartments
        row(units=5, pgi=None, pin="14-01-100-005-0000"),                # an apartment building with no income
        row(units=0, pgi=1000, pin="14-01-100-006-0000"),                # no units
        row(units=9, pgi=90_000, pin="99-99-999-999-0000"),              # cannot be placed in an area
    ]
    area_of = {f"1401100{i:03d}0000": "24" for i in range(1, 7)}
    out = build.summarize(rows, area_of, {"24": 400})
    assert list(out) == ["24"]
    a = out["24"]
    assert a["buildings"] == 4 and a["priced"] == 3     # the unpriced building counts as a building, not as priced
    assert a["units"] == 60                              # priced buildings only: the median and coverage share a base
    assert a["median_pgi_per_unit_month"] == 1000        # median of 1000, 2000, 1000
    assert a["households"] == 400


def test_summarize_orders_areas_numerically_and_leaves_an_area_with_no_households_as_none():
    rows = [row(pin="14-01-100-001-0000"), row(pin="14-01-100-002-0000")]
    out = build.summarize(rows, {"1401100001" + "0000": "9", "1401100002" + "0000": "10"}, {"10": 5})
    assert list(out) == ["9", "10"] and out["9"]["households"] is None


def test_only_multifamily_property_types_are_apartments():
    assert build.is_apartment(row(kind="Multifamily-Mixed Use, Primarily Commercial"))
    assert not build.is_apartment(row(kind="Hotels-SRO/Motel Standard"))
    assert not build.is_apartment(row(kind="Special-Health Care/HospNursing Home"))
    assert not build.is_apartment(row(kind=None))


# --- the committed artifact ---------------------------------------------------------------------------------------


def test_artifact_is_the_2024_city_reassessment_by_community_area():
    art = rent_mod.load_assessor_artifact()
    assert art["assessor"]["year"] == "2024" and art["assessor"]["dataset"] == "csik-bsws"
    assert art["assessor"]["cycle"] == "city reassessment" and art["assessor"]["as_of"] == "2024-12-31"
    assert art["assessor"]["property_types"] == "Multifamily-*"
    areas = art["community_areas"]
    assert len(areas) == 76 and "37" not in areas      # Fuller Park has no modeled apartment buildings
    assert sum(a["buildings"] for a in areas.values()) > 10_000
    assert all(a["priced"] <= a["buildings"] for a in areas.values())
    assert all(a["households"] for a in areas.values())


def test_artifact_households_are_the_rent_artifacts():
    rent = rent_mod.load_artifact()["community_areas"]
    for a, r in rent_mod.load_assessor_artifact()["community_areas"].items():
        assert r["households"] == rent[a]["households"]


def test_the_loop_is_not_comparable_and_a_normal_area_is_not():
    loop = rent_mod.assessor_model_rent(32)
    assert loop.coverage > 1.0
    west = rent_mod.assessor_model_rent(24)
    assert 0.1 <= west.coverage <= 1.0 and west.priced >= 30


def test_an_area_the_assessor_models_nothing_in_is_a_finding_not_an_error():
    fuller = rent_mod.assessor_model_rent(37)
    assert (fuller.buildings, fuller.priced, fuller.units, fuller.coverage, fuller.median_per_unit_month) == (0, 0, 0, 0.0, None)
    assert fuller.households == 727
    assert rent_mod.assessor_model_rent(999) is None


def test_no_figure_by_bedroom_count_exists_anywhere_in_the_series():
    assert not {"studio", "bedroom", "bedrooms", "1br"} & set(AssessorModelRent.model_fields)
    assert not any("bedroom" in k for r in rent_mod.load_assessor_artifact()["community_areas"].values() for k in r)


def test_missing_assessor_artifact_raises_and_is_listed_as_unchecked(tmp_path, monkeypatch):
    class S:
        data_dir = tmp_path
    monkeypatch.setattr(rent_mod, "get_settings", lambda: S())
    with pytest.raises(RentArtifactError):
        rent_mod.load_assessor_artifact()


@pytest.mark.asyncio
async def test_a_broken_assessor_artifact_names_itself_unchecked_and_keeps_the_acs_rent(monkeypatch):
    def boom(_area):
        raise RentArtifactError("assessor_model_by_area.json is unreadable")
    monkeypatch.setattr(rent_mod, "assessor_model_rent", boom)
    ev = await rent_mod.rent_evidence(24, None)
    assert ev.assessor_model is None and "assessor_model" in ev.unchecked
    assert ev.community_area is not None   # the ACS series is unaffected


@pytest.mark.asyncio
async def test_rent_evidence_carries_the_series_beside_never_inside_the_acs_figures():
    ev = await rent_mod.rent_evidence(24, None)
    assert ev.assessor_model.community_area == 24 and ev.community_area.community_area == 24
    assert ev.assessor_model.year == "2024" and ev.acs_period == "2020–2024"
    assert "assessor_model" not in ev.unchecked


# --- provenance ----------------------------------------------------------------------------------------------------


def model(**kw) -> AssessorModelRent:
    base = dict(community_area=24, buildings=400, priced=398, units=12000, households=20000, coverage=0.6,
                median_per_unit_month=1500, year="2024", cycle="city reassessment", as_of="2024-12-31")
    return AssessorModelRent(**{**base, **kw})


def ctx_with(am: AssessorModelRent | None) -> ContextObject:
    return ContextObject(community_area=24, community_area_name="West Town",
                         neighborhood=NeighborhoodSummary(rent=RentEvidence(assessor_model=am)))


def entry(am: AssessorModelRent) -> dict:
    return _provenance_for(ctx_with(am))[FACT]


def test_the_entry_is_a_government_model_with_its_own_source_period_and_coverage():
    e = entry(model())
    assert (e["tier"], e["method_key"], e["scope"]) == ("official_estimate", "government_model", "community_area")
    assert e["source_id"] == "artifact.assessor_model_by_area" and e["geography"] == "West Town"
    assert e["period"] == "2024 city reassessment" and e["as_of"] == "2024-12-31" and e["as_of_basis"] == "tax_year"
    assert e["coverage"] == {"n": 398, "share": 0.6, "universe": "renter households with cash rent", "unit": "buildings", "sample": "area_sample"}
    assert "precision" not in e or not e["precision"]            # the Assessor publishes no margin
    assert e["confidence"] == "standard" and "acs" not in e["source_id"]
    assert "Not an asking or achieved rent" in e["note"] and e["method_params"]["year"] == "2024"


def test_it_never_shares_an_entry_or_source_with_the_acs_series():
    p = _provenance_for(ctx_with(model()))
    assert [k for k in p if k.startswith("area.rent.")] == [FACT]
    assert p[FACT]["source_id"] != "artifact.rent_by_area"


@pytest.mark.parametrize("share, n, state, reason", [
    (0.6, 398, "standard", None),
    (0.25, 398, "standard", None),
    (0.2499, 398, "low", "low_coverage"),
    (0.10, 398, "low", "low_coverage"),
    (0.0999, 398, "withheld", "low_coverage"),
    (1.0, 398, "standard", None),            # exactly 100% is not past it
    (1.0001, 398, "withheld", "not_comparable"),
    (2.31, 112, "withheld", "not_comparable"),
    (0.6, 30, "standard", None),
    (0.6, 29, "withheld", "small_sample"),
])
def test_threshold_boundaries_for_the_series(share, n, state, reason):
    e = {"coverage": {"n": n, "share": share, "unit": "buildings", "sample": "area_sample"}, "method_key": "government_model"}
    got, reasons = confidence_state(e)
    assert got == state
    assert (reason in reasons) if reason else not (set(reasons) & {"low_coverage", "not_comparable", "small_sample"})
    assert P.HIDE_COVERAGE_ABOVE == 1.0


def test_not_comparable_is_not_also_called_low_coverage():
    _, reasons = confidence_state({"coverage": {"share": 2.31}})
    assert reasons == ["not_comparable"]


def test_an_artifact_area_with_a_figure_gets_an_entry_and_the_audit_expects_it():
    ev = rent_mod.assessor_model_rent(24)
    ctx = ctx_with(ev)
    p = _provenance_for(ctx)
    assert FACT in p
    payload = {"context": {"neighborhood": {"rent": {"assessor_model": {"median_per_unit_month": ev.median_per_unit_month}}}}}
    assert FACT in expected_fact_ids(payload)
    payload["context"]["neighborhood"]["rent"]["assessor_model"]["median_per_unit_month"] = None
    assert FACT not in expected_fact_ids(payload)


def test_an_area_with_no_modeled_apartments_has_no_entry():
    assert FACT not in _provenance_for(ctx_with(rent_mod.assessor_model_rent(37)))


# --- chat: a withheld figure never reaches the model -------------------------------------------------------------------


@pytest.mark.parametrize("kw, words", [
    (dict(coverage=1.24, median_per_unit_month=2471), "not a comparable set of homes"),
    (dict(coverage=0.05, median_per_unit_month=1002), "covers 5%"),
    (dict(priced=12, coverage=0.5, median_per_unit_month=1100), "only 12 buildings"),
])
def test_withheld_series_is_cleared_and_explained(kw, words):
    ctx = ctx_with(model(**kw))
    value = f'"median_per_unit_month": {kw["median_per_unit_month"]}'
    assert value in _build_user_text(ctx, "q")
    withhold_low_evidence(ctx, _provenance_for(ctx))
    assert ctx.neighborhood.rent.assessor_model.median_per_unit_month is None
    (w,) = ctx.withheld_figures
    assert w.fact_id == FACT and words in w.reason
    assert value not in _build_user_text(ctx, "q")


def test_clear_figure_finds_the_series_and_reports_a_miss():
    ctx = ctx_with(model())
    assert _clear_figure(ctx, FACT) is True and ctx.neighborhood.rent.assessor_model.median_per_unit_month is None
    assert _clear_figure(ctx_with(None), FACT) is False


def test_a_standard_figure_survives_into_the_context_and_is_named_by_the_prompt_rule_not_a_note():
    """Tier C in a standard state is quiet by policy (``_NOTED_TIERS``); the prompt rule carries the naming."""
    ctx = ctx_with(model())
    withhold_low_evidence(ctx, _provenance_for(ctx))
    assert ctx.withheld_figures is None
    assert ctx.neighborhood.rent.assessor_model.median_per_unit_month == 1500


def test_the_sources_footer_names_the_model_and_says_it_is_not_a_market_rent():
    ctx = ctx_with(model())
    footer = build_sources_footer(_provenance_for(ctx), [], None)
    assert "Assessor" in footer and "not a market rent" in footer and "2024 city reassessment" in footer


def test_the_prompt_keeps_the_series_apart_and_forbids_a_bedroom_rent():
    rule = SYNTHESIZER_SYSTEM[SYNTHESIZER_SYSTEM.index("`rent.assessor_model`"):]
    for phrase in ("SEPARATE series", "never a market, asking or achieved rent", "NEVER average, blend",
                   "NEVER give it by bedroom count", "`priced`", "`coverage`", "withheld_figures"):
        assert phrase in rule


# --- the report shows no rent ----------------------------------------------------------------------------------------------


def test_the_report_does_not_list_the_series_as_a_source_it_used():
    from backend.models import ReportData
    from backend.report_i18n import make_translator
    from backend.report_provenance import entries_for_report, sources_rows

    report = ReportData(context=ctx_with(model()), resolved_pin="14313180131001", resolved_confidence="authoritative")
    entries = entries_for_report(report)
    assert FACT not in entries
    assert "artifact.assessor_model_by_area" not in {r["source_id"] for r in sources_rows(entries, make_translator("en"))}


# --- the data-health registry and the age check -----------------------------------------------------------------------------------


def test_registry_lists_the_artifact_and_its_fact():
    from backend.data_health.registry import BY_ID
    spec = BY_ID["artifact.assessor_model_by_area"]
    assert spec.fact_keys == (FACT,) and spec.tier == "official_estimate" and spec.kind == "artifact"
    assert spec.locator == "ingestion/data/assessor_model_by_area.json"


def test_age_check_is_ok_when_fresh_and_warns_when_the_next_reassessment_is_due(tmp_path):
    (tmp_path / "ingestion/data").mkdir(parents=True)
    side = tmp_path / "ingestion/data/assessor_model_by_area.meta.json"
    side.write_text(json.dumps({"built_at": "2026-10-28", "assessor_year": "2024"}))
    assert artifacts.check_assessor_model(date(2026, 11, 1), tmp_path).state == "ok"
    due = artifacts.check_assessor_model(date(2027, 3, 1), tmp_path)
    assert due.state == "warn" and "2027 reassessment is due" in due.message
    assert artifacts.check_assessor_model(date(2029, 12, 1), tmp_path).state == "warn"
    assert artifacts.check_assessor_model(date(2031, 1, 1), tmp_path).state == "alarm"


def test_age_check_warns_without_a_sidecar(tmp_path):
    assert artifacts.check_assessor_model(date(2026, 11, 1), tmp_path).state == "warn"


def test_the_repo_artifact_passes_its_own_age_check_today():
    c = artifacts.check_assessor_model(date(2026, 11, 1))
    assert c.state == "ok", c.message


def test_state_audit_covers_every_area_and_names_the_loop_and_fuller_park():
    from eval.assessor_model_states import judge

    out = judge()
    assert out["areas"] == 77 and sum(out["by_state"].values()) == 77
    assert out["not_standard"]["32"] == ("withheld", ["not_comparable"])
    assert out["not_standard"]["37"][0] == "no figure"
    assert out["by_state"]["standard"] > 40          # most areas show a figure
