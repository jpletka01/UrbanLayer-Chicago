"""Which edge of a lot is its front? Measured on the fixed 100-address lot panel (decision Item 124, M3).

Offline, no network, no model. Reads the County's newest lot outline per PIN from a local PTAXSIM copy and compares:

* ``shorter``: today's report rule (`report_builder._classify_edges`): of the two edge directions, the shorter
  group is front/rear and its shortest segment is the front;
* ``grid``: Chicago's address grid (`report_builder.grid_front`): the address's direction letter says which way the
  street runs (N/S streets run north-south, E/W streets east-west) and its parity which side of the street the lot is
  on (even numbers on the north and west sides), so the front is the lot edge facing the street. Diagonal and
  unparseable addresses get no answer.

Also counts how many outlines yield a setback footprint before and after merging the straight runs PTAXSIM
splits into short segments.

    python -m eval.front_edge --ptaxsim /path/to/ptaxsim.db [--panel eval/lot_panel.json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter

from backend.models import ZoningStandards
from backend.report_builder import (
    _classify_edges, _compute_inset_polygon, envelope_geometry, grid_front, merge_collinear,
)


def _ring(wkt: str) -> list[list[float]] | None:
    if not wkt.startswith("POLYGON"):
        return None
    inner = wkt[wkt.index("((") + 2: wkt.index(")")]
    return [[float(x) for x in p.split()] for p in inner.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ptaxsim", required=True)
    ap.add_argument("--panel", default="eval/lot_panel.json")
    args = ap.parse_args()
    panel = json.load(open(args.panel))["addresses"]
    con = sqlite3.connect(f"file:{args.ptaxsim}?mode=ro", uri=True)
    std = ZoningStandards(zone_class="RT-4", front_setback_ft=15, side_setback_ft=2, rear_setback_ft=30,
                          extraction_confidence="definitions")
    c: Counter = Counter()
    rows = []
    for a in panel:
        pin10 = a["truth_pin"][:10]
        r = con.execute(
            "SELECT geometry FROM pin_geometry_raw WHERE pin10 = ? ORDER BY start_year DESC LIMIT 1", (pin10,)
        ).fetchone()
        ring = _ring(r[0]) if r else None
        if not ring:
            c["no_outline"] += 1
            continue
        c["outline"] += 1
        raw_edges = _classify_edges(ring, 15, 2, 30)
        if _compute_inset_polygon(ring, raw_edges):
            c["footprint_raw"] += 1
        merged = merge_collinear(ring)
        c[f"edges_{min(len(merged) - 1, 7)}"] += 1
        env = envelope_geometry({"type": "Polygon", "coordinates": [ring]}, std, a["address"])
        c[f"method_{env['method'] if env else 'none'}"] += 1
        if env and env["footprint"]:
            c["footprint_merged"] += 1
        if env and not env["approximate"]:
            c["plain"] += 1
        edges = _classify_edges(merged, 15, 2, 30)
        shorter = next((i for i, e in enumerate(edges) if e.get("role") == "front"), None)
        grid = grid_front(merged, a["address"])
        if grid is None:
            c["grid_none"] += 1
            verdict = "grid_none"
        elif shorter is None:
            verdict = "shorter_none"
            c["shorter_none"] += 1
        elif grid == shorter:
            verdict = "agree"
            c["agree"] += 1
        else:
            verdict = "disagree"
            c["disagree"] += 1
        rows.append({"address": a["address"], "pin": a["truth_pin"], "edges": len(merged) - 1, "verdict": verdict})
    print(json.dumps({"counts": dict(sorted(c.items())), "disagree": [r for r in rows if r["verdict"] == "disagree"]},
                     indent=1))


if __name__ == "__main__":
    main()
