"""How much of a census tract's figures does the confidence standard fade or withhold in chat?

Fetches a fixed spread of Chicago tracts from Census Reporter (free, public; no model calls), runs each
through the chat path's provenance + ``withhold_low_evidence``, and reports per figure how many tracts are
``standard``, ``low`` (faded) and ``withheld`` (removed from the model's context and the sidebar).

The tract list is a spread of Cook County codes (lakefront, north, west, south, Loop, far south); codes the
Census has no tract for answer 400 and are skipped, so the "with data" count is what the numbers rest on.

Usage:  PYTHONPATH=. python -m eval.tract_confidence
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter, defaultdict

from backend.main import _provenance_for
from backend.models import CensusTractDemographics, ContextObject, NeighborhoodSummary
from backend.provenance import withhold_low_evidence

RANGES = [
    (10100, 10900), (20100, 20700), (30100, 30600), (80100, 80500), (242000, 242700), (310100, 310700),
    (420100, 420600), (530100, 530600), (670100, 670500), (710100, 710500), (831000, 831600), (843500, 843900),
]
TRACT_CODES = [c for lo, hi in RANGES for c in range(lo, hi, 100)]


def tally(tracts: list[CensusTractDemographics]) -> dict:
    """``{"figures": Counter, "by_field": {field: Counter}, "tracts_with_withheld": int, "tracts": int}``."""
    figures: Counter = Counter()
    by_field: dict[str, Counter] = defaultdict(Counter)
    with_withheld = 0
    for t in tracts:
        ctx = ContextObject(community_area=1, neighborhood=NeighborhoodSummary(census_tract=t))
        prov = withhold_low_evidence(ctx, _provenance_for(ctx))
        any_withheld = False
        for fact, e in prov.items():
            if fact.startswith("area.tract."):
                figures[e["confidence"]] += 1
                by_field[fact.rsplit(".", 1)[1]][e["confidence"]] += 1
                any_withheld |= e["confidence"] == "withheld"
        with_withheld += any_withheld
    return {"figures": figures, "by_field": dict(by_field), "tracts_with_withheld": with_withheld, "tracts": len(tracts)}


async def _fetch_all() -> list[CensusTractDemographics]:
    """One tract at a time, a second apart: Census Reporter answers 429 ("too fast") to a burst, and a
    blocked client returns no tract at all, which would read as "no data" in the numbers."""
    from backend.retrieval.neighborhood.census_tract import fetch_census_tract

    out = []
    for code in TRACT_CODES:
        try:
            t = await fetch_census_tract(f"17031{code:06d}")
        except Exception:
            t = None
        if t is not None:
            out.append(t)
        await asyncio.sleep(1.0)
    return out


def report(r: dict) -> str:
    total = sum(r["figures"].values()) or 1
    lines = [
        f"tracts with data: {r['tracts']} of {len(TRACT_CODES)} codes",
        "figures: " + ", ".join(f"{k} {r['figures'][k]} ({r['figures'][k] / total:.0%})" for k in ("standard", "low", "withheld")),
        f"tracts with at least one withheld figure: {r['tracts_with_withheld']} of {r['tracts']}",
        "by figure (withheld first):",
    ]
    for f, c in sorted(r["by_field"].items(), key=lambda kv: (-kv[1]["withheld"], -kv[1]["low"], kv[0])):
        lines.append(f"  {f:26s} standard {c['standard']:3d}  low {c['low']:3d}  withheld {c['withheld']:3d}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(tally(asyncio.run(_fetch_all()))))
    sys.stdout.flush()
    os._exit(0)  # the shared HTTP client keeps the process alive otherwise
