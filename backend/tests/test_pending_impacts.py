"""WS2 PR3: pending Title 17 text amendments that could change a rule the Profile uses.

Truth under test: a proposal is named only through a committed human review of its CURRENT record
and a deterministic parcel match; a title keyword never relevance-matches; a missing, outdated or
unavailable review never reads as "none"; and nothing here changes a current-law answer.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.data_health import probes
from backend.data_health.evaluate import ProbeResult
from backend.data_health.registry import BY_ID
from backend.legislation import impacts, upcoming
from backend.legislation.pending_store import MatterRow, Snapshot, Store
from backend.provenance import FACTS, text_impact_entries


FIX = Path(__file__).parent / "fixtures" / "clerk" / "pending_title17_text_2026-10-28.json"
NOW = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
POPULATION = json.loads(FIX.read_text())["matters"]
REVIEWS = impacts.load_reviews()
RAW_REVIEWS = json.loads(impacts.REVIEW_FILE.read_text())["reviews"]


def _matters_from_fixture() -> list[impacts.PendingText]:
    return [
        impacts.PendingText(
            matter_id=m["matter_id"], lifecycle_id=m["lifecycle_id"], record_number=m["record_number"],
            title=m["title"], status=m["status"], sub_status=m["sub_status"],
            introduced_at=m["introduced_at"], latest_action_at=None,
            url=f"https://chicityclerkelms.chicago.gov/Matter/?matterId={m['matter_id']}",
        )
        for m in POPULATION
    ]


def _parcel(zone, *, overlays=(), facts=(), address=None) -> impacts.ParcelFacts:
    ids = frozenset(facts)
    return impacts.ParcelFacts(
        zone_class=zone, overlay_types=tuple(overlays), address=address, fact_ids=ids,
        entries={f: {"label": FACTS[f].label if f in FACTS else f, "value": "x", "section": "17-0-0000"} for f in ids},
    )


def _hits(parcel) -> dict[str, set[str]]:
    found = impacts.impacts_for(_matters_from_fixture(), REVIEWS, parcel)
    return {i.record_number: {e.id for e in i.effects} for i in found}


R_FACTS = ("zoning.district", "zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit", "zoning.unit_yield", "zoning.adu")


# --- the committed review file ----------------------------------------------------------------

def test_every_recorded_pending_title17_matter_has_a_current_valid_review():
    assert len(POPULATION) == 48
    for m in POPULATION:
        review = RAW_REVIEWS.get(m["lifecycle_id"])
        assert review is not None, m["record_number"]
        assert review["reviewed_record"] == m["record_number"], m["record_number"]
        assert " ".join(review["title"].split()) == m["title"], m["record_number"]
        assert review["url"].endswith(m["matter_id"])
        assert impacts.validate_review(m["lifecycle_id"], review) == []
    assert len(REVIEWS) == len(RAW_REVIEWS) == len(POPULATION)


def test_only_an_ordinance_basis_review_carries_impacts_and_never_an_eds():
    for lid, review in RAW_REVIEWS.items():
        if review["impacts"]:
            assert review["basis"] == "ordinance", lid
            assert review["summary"], lid
        else:
            assert review["no_impact_reason"], lid
        blob = json.dumps(review).lower()
        assert "economic disclosure" not in blob and " eds" not in blob and "eds." not in blob, lid
        assert "disclosure" not in (review.get("source_attachment") or "").lower(), lid


def test_every_impact_names_title_17_sections_known_facts_and_a_parcel_condition():
    known = impacts.known_fact_ids()
    for lid, review in RAW_REVIEWS.items():
        for imp in review["impacts"]:
            assert imp["sections"] and all(s.startswith("17-") for s in imp["sections"]), (lid, imp["id"])
            assert set(imp["fact_ids"]) <= known
            assert imp["applies_when"], (lid, imp["id"])
            assert imp["reach"] in impacts.REACH
            assert "will " not in imp["could_change"].lower().split("would")[0]  # proposals "would", never "will"


def test_a_title_only_review_cannot_carry_an_impact_and_an_invalid_entry_is_ignored(monkeypatch, tmp_path):
    bad = {
        **RAW_REVIEWS["O2026-0028842"], "basis": "title",
    }
    assert any("ordinance-basis" in p for p in impacts.validate_review("X", bad))
    ok_lid = "O2026-0029476"
    broken = {**RAW_REVIEWS[ok_lid], "impacts": [{"id": "a", "sections": ["4-4-315"], "fact_ids": ["nope"],
                                                  "applies_when": {}, "reach": "parcel", "could_change": "x"}],
              "basis": "ordinance", "summary": "s", "no_impact_reason": None}
    assert impacts.validate_review(ok_lid, broken)
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps({"reviews": {ok_lid: broken, "O2026-0028842": RAW_REVIEWS["O2026-0028842"]}}))
    monkeypatch.setattr(impacts, "REVIEW_FILE", path)
    loaded = impacts.load_reviews()
    assert set(loaded) == {"O2026-0028842"}  # the invalid one is dropped, so its matter reads unreviewed


# --- deterministic parcel relevance: fixed relevant and unrelated controls -------------------------

def test_unrelated_manufacturing_parcel_outside_transit_gets_no_proposal():
    assert _hits(_parcel("M2-2", facts=("zoning.district", "zoning.far"))) == {}


def test_transit_served_manufacturing_parcel_matches_only_the_transit_parking_proposal():
    # The live 1704 N Milwaukee Ave shape: M1-2 with the CTA TOD overlay.
    hits = _hits(_parcel("M1-2", overlays=("tod_cta", "adu_area"),
                         facts=("zoning.district", "zoning.far", "zoning.tod_benefits"),
                         address="1704 N Milwaukee Ave"))
    assert hits == {"O2026-0026265": {"transit-parking"}}


def test_rt_district_matches_the_lot_area_and_far_counting_proposal_not_the_rs3_one():
    hits = _hits(_parcel("RT-4", facts=R_FACTS))
    assert hits["O2026-0028842"] == {"mla-rt-rm", "far-family-units"}
    assert "O2026-0026329" not in hits and "O2023-2075" not in hits
    assert hits["O2026-0028836"] == {"bay-window-far"}


def test_rm6_adds_the_premium_effect_and_an_rm45_does_not():
    assert "far-premium-rm6" in _hits(_parcel("RM-6", facts=R_FACTS))["O2026-0028842"]
    assert "far-premium-rm6" not in _hits(_parcel("RM-4.5", facts=R_FACTS))["O2026-0028842"]


def test_rs3_inside_an_adu_area_matches_the_two_unit_exemption_only():
    hits = _hits(_parcel("RS-3", overlays=("adu_area",), facts=R_FACTS))
    assert hits["O2026-0026329"] == {"rs3-adu-mla"}
    assert "O2023-2075" not in hits and "O2024-0014096" not in hits  # already in an ADU area
    assert "O2026-0028842" not in hits  # RS1-RS3 standards are unchanged by it


def test_rs3_outside_an_adu_area_matches_the_citywide_proposal_and_an_untested_boundary_one():
    found = {i.record_number: i for i in impacts.impacts_for(_matters_from_fixture(), REVIEWS, _parcel("RS-3", facts=R_FACTS))}
    assert found["O2023-2075"].effects[0].reach == "parcel"
    assert found["O2024-0014096"].effects[0].reach == "untested"
    assert "Central Business District" in found["O2023-2075"].effects[0].reach_note
    assert "O2026-0026329" not in found


def test_dash_3_commercial_transit_parcel_gets_the_transit_increase_effects():
    hits = _hits(_parcel("B3-3", overlays=("tod_cta",), facts=R_FACTS + ("zoning.tod_benefits",)))
    assert hits["O2026-0028842"] >= {"mla-bc", "far-family-units", "transit-mla-reduction"}
    assert hits["O2026-0026265"] == {"transit-parking", "transit-increases"}
    assert hits["O2025-0016750"] == {"bc-conversion-units"}


def test_b2_is_not_in_the_conversion_unit_proposal_and_a_dash_2_gets_no_transit_increase():
    assert "O2025-0016750" not in _hits(_parcel("B2-2", facts=R_FACTS))
    hits = _hits(_parcel("B3-2", overlays=("tod_cta",), facts=R_FACTS + ("zoning.tod_benefits",)))
    assert "transit-mla-reduction" not in hits["O2026-0028842"]
    assert hits["O2026-0026265"] == {"transit-parking"}


def test_d_16_district_gets_the_bonus_cap_proposal():
    hits = _hits(_parcel("DX-16", facts=("zoning.district", "zoning.far", "zoning.min_lot_area_per_unit", "zoning.unit_yield")))
    assert hits["O2023-0005667"] == {"d16-mla-cap"}
    assert "mla-d" in hits["O2026-0028842"]
    assert "O2023-0005667" not in _hits(_parcel("DX-12", facts=("zoning.district", "zoning.far", "zoning.min_lot_area_per_unit")))


def test_a_proposal_needs_the_profile_to_actually_show_the_fact_it_could_change():
    # Same RT district, but this Profile shows none of the mapped facts (e.g. a fallback zone table).
    assert _hits(_parcel("RT-4", facts=("zoning.district",))) == {}


@pytest.mark.parametrize("address,record,effect", [
    ("2931 N Milwaukee Ave", "O2025-0016007", "ped-street-milwaukee"),
    ("1050 W Diversey Pkwy", "O2026-0029431", "ped-street-diversey"),
    ("1700 W Lawrence Ave", "O2026-0026237", "tod-street-lawrence"),
    ("3700 N Western Ave", "O2026-0026261", "tod-street-western"),
    ("4500 N Ravenswood Ave", "O2026-0026239", "tod-street-ravenswood"),
])
def test_street_designations_match_by_address_range(address, record, effect):
    hits = _hits(_parcel("B3-2", address=address))
    assert hits[record] == {effect}


@pytest.mark.parametrize("address", [
    "1601 N Milwaukee Ave", "3000 N Milwaukee Ave", "5200 N Western Ave", "2200 W Foster Ave", "1100 N Diversey Ave",
])
def test_addresses_outside_every_reviewed_segment_match_no_street_designation(address):
    found = _hits(_parcel("B3-2", address=address))
    assert not [r for r in found if r in {"O2025-0016007", "O2026-0029431", "O2026-0026237", "O2026-0026261", "O2026-0026239"}]


def test_each_effect_names_the_current_fact_beside_the_proposal_without_changing_it():
    parcel = impacts.ParcelFacts(
        zone_class="RT-4", overlay_types=(), address=None, fact_ids=frozenset(R_FACTS),
        entries={"zoning.min_lot_area_per_unit": {"label": "Minimum lot area per dwelling unit for RT-4", "value": "1,000 sq ft", "section": "17-2-0303-A"}},
    )
    found = {i.record_number: i for i in impacts.impacts_for(_matters_from_fixture(), REVIEWS, parcel)}
    effect = next(e for e in found["O2026-0028842"].effects if e.id == "mla-rt-rm")
    fact = next(f for f in effect.affected if f.fact_id == "zoning.min_lot_area_per_unit")
    assert (fact.current_value, fact.section) == ("1,000 sq ft", "17-2-0303-A")
    assert found["O2026-0028842"].basis == "ordinance" and found["O2026-0028842"].url.startswith("https://chicityclerkelms")
    assert found["O2026-0028842"].status == "4-In Committee"  # pending only because the Clerk says so


# --- review state: missing / outdated / unavailable never read as "none" ------------------------

def _store(tmp_path, matters, *, checked=NOW):
    path = tmp_path / "pending.db"
    rows = tuple(
        MatterRow(
            matter_id=m.matter_id, lifecycle_id=m.lifecycle_id, record_number=m.record_number,
            original_record_number=None, status=m.status, sub_status=m.sub_status, category="MUNICIPAL CODE AMENDMENTS",
            matter_type="Ordinance", title=m.title, introduced_at=datetime.fromisoformat(m.introduced_at) if m.introduced_at else None,
            created_at=None, last_published_at=None, superseded_by=None, source_url=m.url, title_parse_status=None,
            application_number=None, touches_title17=True,
        )
        for m in matters
    )
    with Store(path) as store:
        store.replace(Snapshot(
            checked_at=checked, matters=rows, candidate_count=len(rows), detail_count=len(rows), lifecycle_collapses=0,
            excluded_non_pending=0, excluded_attachments=0, placement_ready_count=0, partial_title_count=0, unparsed_title_count=0,
        ))
    return path


def test_fully_reviewed_population_is_complete_and_a_clean_parcel_is_a_healthy_none(tmp_path):
    path = _store(tmp_path, _matters_from_fixture())
    found, review = impacts.for_parcel(
        path, summary_status="ready", checked_at="2026-10-28T04:18:05+00:00",
        parcel=_parcel("M2-2", facts=("zoning.district", "zoning.far")), now=NOW,
    )
    assert found == []
    assert (review.status, review.pending_count, review.reviewed_count, review.unreviewed) == ("complete", 48, 48, [])
    assert review.review_provenance.confidence == "standard"


def test_a_new_unreviewed_matter_makes_the_review_incomplete_even_when_its_title_mentions_a_profile_rule(tmp_path):
    new = impacts.PendingText(
        matter_id="NEW-1", lifecycle_id="O2026-0030001", record_number="O2026-0030001",
        title="Amendment of Municipal Code Title 17 by modifying minimum lot area per unit and floor area ratio",
        status="4-In Committee", sub_status="Referred", introduced_at="2026-10-14T15:00:00+00:00", latest_action_at=None,
        url="https://chicityclerkelms.chicago.gov/Matter/?matterId=NEW-1",
    )
    path = _store(tmp_path, [*_matters_from_fixture(), new])
    found, review = impacts.for_parcel(
        path, summary_status="ready", checked_at="2026-10-28T04:18:05+00:00",
        parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    assert "O2026-0030001" not in {i.record_number for i in found}  # no keyword inference
    assert review.status == "incomplete" and review.pending_count == 49 and review.reviewed_count == 48
    assert [(u.record_number, u.reason, u.waiting_days) for u in review.unreviewed] == [("O2026-0030001", "unreviewed", 14)]
    assert review.overdue is False
    assert review.review_provenance.confidence == "low"


def test_a_newer_substitute_outdates_the_review_of_the_older_record(tmp_path):
    m = next(x for x in _matters_from_fixture() if x.record_number == "O2026-0028842")
    substitute = impacts.PendingText(**{**m.__dict__, "record_number": "SO2026-0028842", "matter_id": "SUB-1"})
    path = _store(tmp_path, [substitute])
    found, review = impacts.for_parcel(
        path, summary_status="ready", checked_at="2026-10-28T04:18:05+00:00",
        parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    assert found == []  # the reviewed text is no longer the live text
    assert review.status == "incomplete" and review.unreviewed[0].reason == "outdated"


def test_a_substitute_is_one_lifecycle_and_its_review_follows_the_current_record():
    sub = next(x for x in _matters_from_fixture() if x.record_number == "SO2024-0014404")
    assert sub.lifecycle_id == "O2024-0014404"  # keyed by the lifecycle, reviewed at the substitute
    assert impacts.review_state(sub, REVIEWS) == "reviewed"


def test_an_unavailable_snapshot_is_unavailable_never_an_empty_list(tmp_path):
    found, review = impacts.for_parcel(
        tmp_path / "missing.db", summary_status="unavailable", checked_at=None, parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    assert found == [] and review.status == "unavailable" and review.pending_count == 0
    found, review = impacts.for_parcel(
        tmp_path / "missing.db", summary_status="ready", checked_at="2026-10-28T04:18:05+00:00",
        parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    assert found == [] and review.status == "unavailable"


def test_a_stale_snapshot_keeps_its_reviewed_impacts_with_a_low_confidence_review(tmp_path):
    path = _store(tmp_path, _matters_from_fixture(), checked=NOW - timedelta(days=5))
    found, review = impacts.for_parcel(
        path, summary_status="stale", checked_at="2026-10-23T18:00:00+00:00", parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    assert found and review.status == "complete" and review.review_provenance.confidence == "low"


def test_the_serialized_response_carries_no_attachment_or_eds_text(tmp_path):
    path = _store(tmp_path, _matters_from_fixture())
    found, review = impacts.for_parcel(
        path, summary_status="ready", checked_at="2026-10-28T04:18:05+00:00", parcel=_parcel("B3-3", overlays=("tod_cta",), facts=R_FACTS + ("zoning.tod_benefits",)), now=NOW,
    )
    blob = json.dumps([i.model_dump() for i in found] + [review.model_dump()]).lower()
    assert "economic disclosure" not in blob and "attachment" not in blob and ".pdf" not in blob


# --- the daily-snapshot reader, provenance and the review backlog ------------------------------

def test_summary_for_still_serves_filings_and_leaves_text_fields_unset_until_the_parcel_facts_exist(tmp_path):
    path = _store(tmp_path, _matters_from_fixture())
    summary = upcoming.summary_for(path, lat=41.9, lon=-87.68, pin=None, address=None, authoritative_pin=False, now=NOW)
    assert summary.status == "ready" and summary.text_impacts == [] and summary.text_review is None


def test_provenance_splits_the_clerk_record_from_our_reviewed_relevance(tmp_path):
    path = _store(tmp_path, _matters_from_fixture())
    summary = upcoming.summary_for(path, lat=41.9, lon=-87.68, pin=None, address=None, authoritative_pin=False, now=NOW)
    summary.text_impacts, summary.text_review = impacts.for_parcel(
        path, summary_status=summary.status, checked_at=summary.checked_at,
        parcel=_parcel("RT-4", facts=R_FACTS), now=NOW,
    )
    entries = text_impact_entries(summary, "2026-10-28")
    assert set(entries) == {"regulatory.upcoming_zoning.text_impacts", "regulatory.upcoming_zoning.relevance"}
    assert entries["regulatory.upcoming_zoning.text_impacts"]["source_id"] == "chi.clerk.legislation"
    relevance = entries["regulatory.upcoming_zoning.relevance"]
    assert relevance["source_id"] == "internal.pending_impact_review" and relevance["tier"] == "our_calculation"
    assert relevance["coverage"]["n"] == 48 and relevance["coverage"]["share"] == 1.0
    summary.text_review = impacts.unavailable_review()
    assert text_impact_entries(summary, "2026-10-28") == {}


def test_backlog_orders_the_oldest_unreviewed_first_and_counts_outdated(tmp_path):
    old = impacts.PendingText("OLD", "O2026-0030002", "O2026-0030002", "t", "4-In Committee", "Referred",
                              "2026-08-01T15:00:00+00:00", None, "https://x")
    new = impacts.PendingText("NEW", "O2026-0030003", "O2026-0030003", "t", "4-In Committee", "Referred",
                              "2026-10-20T15:00:00+00:00", None, "https://x")
    rows = impacts.backlog([new, old], REVIEWS, date(2026, 10, 28))
    assert [(r["record"], r["waiting_days"]) for r in rows] == [("O2026-0030002", 88), ("O2026-0030003", 8)]


def _probe(monkeypatch, tmp_path, matters, *, today=date(2026, 10, 28), checked=NOW, reviews=None):
    from backend.config import get_settings

    path = _store(tmp_path, matters, checked=checked)
    monkeypatch.setattr(get_settings(), "pending_legislation_path", path)
    if reviews is not None:
        rpath = tmp_path / "reviews.json"
        rpath.write_text(json.dumps({"reviews": reviews}))
        monkeypatch.setattr(impacts, "REVIEW_FILE", rpath)
    ctx = type("Ctx", (), {"today": today})()
    import asyncio

    return asyncio.run(probes.probe_pending_impact_review(BY_ID["internal.pending_impact_review"], ctx))


def test_probe_is_quiet_when_every_pending_proposal_is_reviewed(monkeypatch, tmp_path):
    res = _probe(monkeypatch, tmp_path, _matters_from_fixture())
    assert isinstance(res, ProbeResult) and res.findings == []
    assert "48 reviewed" in res.info


def test_probe_warns_after_14_days_alarms_after_45_and_flags_a_replaced_review(monkeypatch, tmp_path):
    mk = lambda rec, intro: impacts.PendingText(rec, rec, rec, "t", "4-In Committee", "Referred", intro, None, "https://x")  # noqa: E731
    warn = _probe(monkeypatch, tmp_path, [mk("O2026-0030004", "2026-10-07T15:00:00+00:00")], reviews={})
    assert [(f.level, "O2026-0030004" in f.text) for f in warn.findings] == [("warn", True)]
    alarm = _probe(monkeypatch, tmp_path, [mk("O2026-0030005", "2026-09-01T15:00:00+00:00")], reviews={})
    assert [f.level for f in alarm.findings] == ["alarm"]
    fresh = _probe(monkeypatch, tmp_path, [mk("O2026-0030006", "2026-10-20T15:00:00+00:00")], reviews={})
    assert fresh.findings == []  # inside the grace period
    m = next(x for x in _matters_from_fixture() if x.record_number == "O2026-0028842")
    sub = impacts.PendingText(**{**m.__dict__, "record_number": "SO2026-0028842", "matter_id": "SUB-2"})
    outdated = _probe(monkeypatch, tmp_path, [sub], reviews={"O2026-0028842": RAW_REVIEWS["O2026-0028842"]})
    assert outdated.findings and "outdated" in outdated.findings[0].text


def test_probe_makes_no_judgement_without_a_fresh_pending_snapshot(monkeypatch, tmp_path):
    res = _probe(monkeypatch, tmp_path, _matters_from_fixture(), checked=NOW - timedelta(days=20), reviews={})
    assert res.findings == [] and "cannot be judged" in res.info


def test_probe_alarms_on_an_invalid_review_entry(monkeypatch, tmp_path):
    res = _probe(monkeypatch, tmp_path, _matters_from_fixture(), reviews={"O2026-0028842": {**RAW_REVIEWS["O2026-0028842"], "basis": "title"}})
    assert any(f.level == "alarm" and "invalid" in f.text for f in res.findings)


def test_registry_lists_the_review_source_and_the_fact_it_supplies():
    spec = BY_ID["internal.pending_impact_review"]
    assert "regulatory.upcoming_zoning.relevance" in spec.fact_keys and spec.availability_only
    assert "regulatory.upcoming_zoning.text_impacts" in BY_ID["chi.clerk.legislation"].fact_keys


def test_current_figures_carry_the_units_the_profile_value_omits():
    assert impacts._shown("zoning.min_lot_area_per_unit", 1000) == "1,000 sq ft"
    assert impacts._shown("zoning.min_lot_area_per_unit", "1,000") == "1,000 sq ft"
    assert impacts._shown("zoning.unit_yield", 30) == "30 units by lot area"
    assert impacts._shown("zoning.far", 1.2) == 1.2  # no unit rule: shown as the Profile has it
    assert impacts._shown("zoning.min_lot_area_per_unit", "no minimum") == "no minimum"
