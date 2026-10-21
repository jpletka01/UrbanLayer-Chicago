"""WS0 M3: every figure a Profile shows has a complete provenance entry.

Runs ``build_provenance`` over the 12 recorded Profile payloads of the parcel kit
(eval/results/2026-10-21-m4/parcel_kit_raw/P*.profile.json, committed) and checks that each fact id the
payload calls for (``expected_fact_ids``, written from the payload's JSON shape) has an entry
with its tier, method, an as-of basis and a date. A figure added to the Profile without an
entry fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.models import ComparablesSummary, ContextObject
from backend.provenance import ProvenanceEntry, build_provenance
from backend.provenance_figures import expected_fact_ids

BASELINE = Path(__file__).resolve().parents[2] / "eval" / "results" / "2026-10-21-m4" / "parcel_kit_raw"
PAYLOADS = sorted(BASELINE.glob("P*.profile.json"))
REQUIRED = ("tier", "method_key", "method", "as_of_basis", "confidence", "query_date", "label", "kind")


def _current(payload: dict) -> dict:
    """The payload as today's endpoint serializes it (computed fields included)."""
    ctx = ContextObject.model_validate(payload["context"])
    return {**payload, "context": ctx.model_dump(exclude_none=True)}


def _provenance(payload: dict) -> dict:
    ctx = ContextObject.model_validate(payload["context"])
    comps = ComparablesSummary.model_validate(payload["comparables"]) if payload.get("comparables") else None
    return build_provenance(
        context=ctx, zone_definition=payload.get("zone_definition"), resolved_pin=payload.get("resolved_pin"),
        resolved_confidence=payload.get("resolved_confidence"), comparables=comps, address_scoped_violations=True,
    )


def test_the_baseline_panel_is_present():
    assert len(PAYLOADS) == 12, "the 12 recorded Profile payloads must stay committed"


@pytest.mark.parametrize("path", PAYLOADS, ids=lambda p: p.name.split(".")[0])
def test_every_present_figure_has_an_entry(path):
    payload = _current(json.loads(path.read_text()))
    prov = _provenance(payload)
    missing = sorted(expected_fact_ids(payload) - set(prov))
    assert not missing, f"{path.name}: figures with no provenance entry: {missing}"


@pytest.mark.parametrize("path", PAYLOADS, ids=lambda p: p.name.split(".")[0])
def test_every_entry_is_complete_and_valid(path):
    for fact, e in _provenance(json.loads(path.read_text())).items():
        for k in REQUIRED:
            assert e.get(k) not in (None, ""), (path.name, fact, k)
        assert e.get("as_of") or e.get("query_date"), (path.name, fact)
        ProvenanceEntry.model_validate({k: v for k, v in e.items() if k in ProvenanceEntry.model_fields})
        if e["tier"] == "our_calculation" and e.get("inputs"):
            assert e.get("basis_tier"), (path.name, fact, "a calculation names the weakest tier of its inputs")


def test_the_panel_exercises_most_figure_families():
    """The coverage claim is only as strong as the figures the panel carries: tract ACS, comps,
    incentives, flags, building facts and the area feed must each appear on at least one parcel."""
    seen: set[str] = set()
    for path in PAYLOADS:
        seen |= expected_fact_ids(_current(json.loads(path.read_text())))
    for fam in ("area.tract.", "property.comps.", "incentive.", "property.flags.", "property.year_built", "area.crime",
                "property.tax_estimate", "zoning.unit_yield", "neighborhood.walkscore", "property.exemptions"):
        assert any(f.startswith(fam) for f in seen), f"no parcel in the panel carries {fam}"


def test_the_audit_aggregates_recorded_payloads():
    """The audit script's arithmetic on the recorded panel: full coverage, tier mix, no errors."""
    from eval.confidence_audit import audit, markdown

    payloads = []
    for path in PAYLOADS:
        pl = _current(json.loads(path.read_text()))
        pl["provenance"] = _provenance(pl)
        pl["address"] = path.name.split(".")[0]
        payloads.append(pl)
    report = audit(payloads)
    assert report["payloads"] == 12 and report["coverage"] == 1.0
    assert report["figures_expected"] == report["figures_with_entry"] > 150
    rent = report["facts"]["area.tract.median_gross_rent"]
    assert rent["expected"] == rent["with_entry"] and rent["tiers"] == {"official_estimate": rent["with_entry"]}
    assert report["facts"]["property.tax_class_norm"]["oldest_as_of"] == "2023-12-31"
    assert "Confidence audit" in markdown(report, "test") and "Figures with no entry" not in markdown(report, "test")
    # a payload missing an entry is reported, with the address
    broken = {**payloads[0], "provenance": {k: v for k, v in payloads[0]["provenance"].items() if k != "property.tax_estimate"}}
    r2 = audit([broken])
    assert r2["facts"]["property.tax_estimate"]["missing_in"] == [broken["address"]] and r2["coverage"] < 1.0
