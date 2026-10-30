"""WS8 Phase 0 slice 3: how often does the Discovery index's building area disagree with the Profile's?

For the fixed 100-address panel (``eval/lot_panel.json``, sampled from Address Points across the seven Chicago
township prefixes), call the real ``/api/scorecard`` (no model calls) and compare, per parcel, the Profile's
building area, lot area and allowed FAR with the Discovery index row for the same PIN.  Each parcel gets the
index's capacity state and the state the same rules give from the Profile's values, so the table says where a
map built from the index would differ from the Profile a user sees.

A parcel counts only when the Profile resolved the panel's own PIN (a nearest-parcel stand-in is set aside as
``pin_mismatch``).  A failed scorecard call is ``fetch_error``, never a disagreement.

Usage:  PYTHONPATH=. python -m eval.capacity_panel --index <discovery_index.db> --base-url http://localhost:8001 \
            [--out eval/results/2026-10-28-ws8/panel_disagreement.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import httpx

from eval.capacity_coverage import classify
from eval.lot_coverage import PANEL_FILE

AGREE_TOLERANCE = 0.05  # areas within 5% of each other agree
CONCURRENCY = 2


def dashed(pin14: str) -> str:
    """"20331000020000" -> "20-33-100-002-0000"."""
    d = pin14.replace("-", "")
    return f"{d[:2]}-{d[2:4]}-{d[4:7]}-{d[7:10]}-{d[10:]}"


def profile_facts(resp: dict) -> dict:
    """The Profile fields the comparison needs, from one /api/scorecard response."""
    prop = (resp.get("context") or {}).get("property") or {}
    return {
        "pin14": prop.get("pin14"),
        "class": prop.get("bldg_class"),
        "bldg_sqft": prop.get("bldg_sqft"),
        "bldg_source": prop.get("bldg_sqft_source"),
        "complex_bldg_sqft": prop.get("complex_bldg_sqft"),
        "land_sqft": prop.get("land_sqft"),
        "land_source": prop.get("land_sqft_source"),
        "allowed_far": (resp.get("zone_definition") or {}).get("far"),
        "zone_fallback": (resp.get("zone_definition") or {}).get("is_fallback"),
        "nearest_unverified": bool(resp.get("nearest_parcel_unverified")),
    }


def area_relation(index_val: float | None, profile_val: float | None) -> str:
    """How two building (or lot) areas relate: agree, differ, only one side has it, or neither does."""
    if not index_val and not profile_val:
        return "both_missing"
    if not index_val:
        return "profile_only"
    if not profile_val:
        return "index_only"
    return "agree" if abs(index_val - profile_val) <= AGREE_TOLERANCE * max(index_val, profile_val) else "differ"


def profile_state(facts: dict, index_attrs: dict | None) -> str:
    """The capacity state the index's rules give from the Profile's values.

    Zoning group and class come from the index row (the Profile shows the same district); a PD or unknown zone has
    no table FAR, which is what ``classify`` keys on."""
    base = dict(index_attrs or {})
    base.update({
        "class": facts.get("class") or base.get("class"),
        "land_sqft": facts.get("land_sqft") or None,
        "bldg_sqft": facts.get("bldg_sqft") or None,
        "density_band": facts.get("allowed_far") or None,
    })
    if base.get("zoning_group") is None and facts.get("allowed_far"):
        base["zoning_group"] = "residential"  # the Profile found a district the index join missed
    if facts.get("class", "") and str(facts["class"]).startswith("1"):
        base["is_vacant"] = True
    return classify(base)


def compare(row: dict, facts: dict | None, index_attrs: dict | None, error: str = "") -> dict:
    out = {"address": row["address"], "truth_pin": row["truth_pin"], "township": row.get("township")}
    if error or facts is None:
        return {**out, "outcome": "fetch_error", "error": error}
    if index_attrs is None:
        return {**out, "outcome": "not_in_index", "profile": facts}
    if facts.get("nearest_unverified") or (facts.get("pin14") or "").replace("-", "") != row["truth_pin"]:
        return {**out, "outcome": "pin_mismatch", "profile": facts}
    return {
        **out,
        "outcome": "compared",
        "class": facts.get("class"),
        "bldg": area_relation(index_attrs.get("bldg_sqft"), facts.get("bldg_sqft")),
        "land": area_relation(index_attrs.get("land_sqft"), facts.get("land_sqft")),
        "far": "agree" if (index_attrs.get("density_band") or None) == (facts.get("allowed_far") or None) else "differ",
        "bldg_source": facts.get("bldg_source"),
        "index_bldg_sqft": index_attrs.get("bldg_sqft"),
        "profile_bldg_sqft": facts.get("bldg_sqft"),
        "complex_bldg_sqft": facts.get("complex_bldg_sqft"),
        "index_state": classify(index_attrs),
        "profile_state": profile_state(facts, index_attrs),
    }


def summarize(results: list[dict]) -> dict:
    compared = [r for r in results if r["outcome"] == "compared"]
    n = len(compared)

    def count(key: str) -> dict:
        return dict(Counter(r[key] for r in compared))

    flips = Counter((r["index_state"], r["profile_state"]) for r in compared if r["index_state"] != r["profile_state"])
    return {
        "panel": len(results),
        "outcomes": dict(Counter(r["outcome"] for r in results)),
        "compared": n,
        "bldg": count("bldg"),
        "land": count("land"),
        "far": count("far"),
        "state_agree": sum(r["index_state"] == r["profile_state"] for r in compared),
        "state_flips": {f"{a} -> {b}": c for (a, b), c in flips.most_common()},
        "bldg_source_when_profile_only": dict(Counter(r["bldg_source"] for r in compared if r["bldg"] == "profile_only")),
    }


def index_rows(path: Path, pins: list[str]) -> dict[str, dict]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    out: dict[str, dict] = {}
    for pin in pins:
        row = con.execute("select attrs from parcels where pin = ?", (dashed(pin),)).fetchone()
        if row:
            out[pin] = json.loads(row[0])
    return out


async def run(index: Path, base_url: str) -> list[dict]:
    panel = json.loads(Path(PANEL_FILE).read_text())["addresses"]
    attrs = index_rows(index, [r["truth_pin"] for r in panel])
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(row: dict, http: httpx.AsyncClient) -> dict:
        async with sem:
            try:
                r = await http.get(f"{base_url}/api/scorecard", params={"address": row["address"]}, timeout=httpx.Timeout(150.0))
                r.raise_for_status()
                facts = profile_facts(r.json())
            except Exception as exc:  # noqa: BLE001
                return compare(row, None, attrs.get(row["truth_pin"]), f"{type(exc).__name__}: {exc}")
        return compare(row, facts, attrs.get(row["truth_pin"]))

    async with httpx.AsyncClient() as http:
        return await asyncio.gather(*[one(r, http) for r in panel])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--base-url", default="http://localhost:8001")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    results = asyncio.run(run(args.index, args.base_url))
    summary = summarize(results)
    print(json.dumps(summary, indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({**summary, "parcels": results}, indent=1, sort_keys=True))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
