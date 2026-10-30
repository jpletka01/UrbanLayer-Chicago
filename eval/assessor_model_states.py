"""How the confidence standard judges the Assessor's modeled apartment income, area by area (WS4 PR3).

Reads the committed ``assessor_model_by_area.json`` (no network, no model) and runs each community area through
``provenance.confidence_state`` exactly as the Profile does: n < 30 priced buildings or coverage under 10% is
withheld, coverage under 25% is faded, coverage above 100% is withheld as not comparable.

Usage:  PYTHONPATH=. python -m eval.assessor_model_states
"""

from __future__ import annotations

import json
from collections import Counter

from backend.provenance import confidence_state
from backend.retrieval.neighborhood import rent


def judge() -> dict:
    states: dict[str, tuple[str, list[str]]] = {}
    for area in sorted(rent.load_artifact()["community_areas"], key=int):
        am = rent.assessor_model_rent(int(area))
        if am is None or am.median_per_unit_month is None:
            states[area] = ("no figure", ["no_modeled_apartments"])
            continue
        states[area] = confidence_state({
            "method_key": "government_model",
            "coverage": {"n": am.priced, "share": am.coverage, "unit": "buildings", "sample": "area_sample"},
        })
    by_state = Counter(s for s, _ in states.values())
    reasons = Counter(r for _, rs in states.values() for r in rs)
    return {
        "areas": len(states), "by_state": dict(by_state), "by_reason": dict(reasons),
        "not_standard": {a: v for a, v in states.items() if v[0] != "standard"},
    }


if __name__ == "__main__":
    out = judge()
    print(json.dumps({k: v for k, v in out.items() if k != "not_standard"}, indent=1))
    print("withheld or faded or without a figure:", sorted(out["not_standard"], key=int))
