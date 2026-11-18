"""Blind owner check for empty public land (decision Item 128, the owner's review of 2026-11-16). No model calls;
localhost only.

    PYTHONPATH=. python -m eval.public_land_label draw [--index backend/data/discovery_index.db]
    PYTHONPATH=. python -m eval.public_land_label serve [--port 8036]
    PYTHONPATH=. python -m eval.public_land_label score

The rule under test (``lot_facts.mark_owner``): a physically empty lot (Item 110) that the Assessor's exempt file
says the City, the CHA or the Cook County Land Bank owns is empty public land, a site with room to build, not an
"exempt institution". **Draw** (seeded 128, ``STRATA``): such lots by owner, the City's split by whether CMAP calls the
lot institutional (a police or fire station's yard?), and as a control the empty lots of the Board of Education,
which stay institutions (school yards?). **Blind**: the rail check's page and machinery (outline, neighbors' own
addresses, streets, footprints around the lot, Street View, the lot from above), never the owner, the source or the
stratum. Labels go to the gitignored ``eval/results/2026-11-16-public-land/labels.json``; ``score`` prints counts.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from eval import empty_land_label as ell
from eval import land_use_label as lul

PANEL = Path("eval/public_land_panel.json")
PAGE = Path(__file__).with_name("public_land_label_page.html")
LABELS = Path("eval/results/2026-11-16-public-land/labels.json")
SEED = 128
STRATA = (("cha", 12), ("city_was_institution", 10), ("city_other", 10), ("land_bank", 8), ("cps_control", 8))
SITE = ("site",)


def stratum_of(r: dict) -> str | None:
    if r.get("unusual") or r.get("infrastructure") or r.get("open_land"):
        return None
    owner = r.get("exempt_owner")
    if r.get("public_land"):
        if owner == "Chicago Housing Authority":
            return "cha"
        if owner == "Cook County Land Bank Authority":
            return "land_bank"
        if owner == "City of Chicago":
            return "city_was_institution" if r.get("cmap_institution") else "city_other"
    if owner and owner.startswith("Chicago Board of Education") and r.get("empty_land") and r.get("institution"):
        return "cps_control"
    return None


def rows_from_index(index: Path, sources: Path) -> list[dict]:
    from backend.discovery.lot_facts import INSTITUTION_CODES, OPEN_LAND_MIN_SHARE

    src = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    inst = {p for p, c, s in src.execute("SELECT pin10, code, share FROM cmap_on_lot")
            if c in INSTITUTION_CODES and s >= OPEN_LAND_MIN_SHARE}
    src.close()
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    out = []
    keys = ("exempt_owner", "public_land", "empty_land", "institution", "unusual", "infrastructure", "open_land",
            "structure", "land_kind", "room_sqft", "zone_class")
    for pin, lat, lon, attrs in db.execute("SELECT pin, lat, lon, attrs FROM parcels WHERE pin LIKE '%0000'"):
        a = json.loads(attrs)
        r = {"pin": pin, "lat": lat, "lon": lon, **{k: a.get(k) for k in keys}}
        r["cmap_institution"] = pin.replace("-", "")[:10] in inst
        out.append(r)
    db.close()
    return out


def draw(index: Path, sources: Path, ptaxsim: Path, out: Path) -> dict:
    rows = rows_from_index(index, sources)
    tmp = out.with_suffix(".rows.json")
    tmp.write_text(json.dumps(rows))
    try:
        pool = lul.draw(tmp, index, sources, ptaxsim, [], out, STRATA, stratum_of, SEED)
    finally:
        tmp.unlink(missing_ok=True)
    by_pin = {r["pin"]: r for r in rows}
    panel = json.loads(out.read_text())
    for lot in panel["lots"]:
        r = by_pin[lot["pin"]]
        lot["truth_keys"] = {k: r.get(k) for k in ("exempt_owner", "structure", "land_kind", "zone_class", "room_sqft",
                                                   "cmap_institution")}
    out.write_text(json.dumps(panel, separators=(",", ":")))
    return pool


def serve(panel_path: Path, port: int) -> None:
    ell.LABELS = LABELS
    ell.PAGE = PAGE
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    panel = json.loads(panel_path.read_text())
    blind = panel_path.with_name(".public_land_panel_blind.json")
    blind.write_text(json.dumps({"lots": [{k: v for k, v in lot.items() if k not in lul.HIDDEN}
                                          for lot in panel["lots"]]}))
    try:
        ell.serve(blind, port)
    finally:
        blind.unlink(missing_ok=True)


def score(panel_path: Path) -> dict:
    """Counts only: per stratum the owner's answers and the share that is a site on its own (Wilson 95%)."""
    panel = json.loads(panel_path.read_text())
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    per: dict[str, Counter] = {}
    for lot in panel["lots"]:
        ans = (labels.get(lot["pin"]) or {}).get("answer") or "unlabeled"
        per.setdefault(lot["stratum"], Counter())[ans] += 1

    def rate(c: Counter) -> dict:
        n = sum(v for k, v in c.items() if k not in ("unlabeled", "cant_tell"))
        k = sum(c[h] for h in SITE)
        return {"site": k, "decided": n, "share": round(k / n, 3) if n else None, "ci95": lul._ci(k, n)}

    rule = sum((per.get(s, Counter()) for s in ("cha", "city_was_institution", "city_other", "land_bank")), Counter())
    return {"labeled": sum(sum(v for k, v in c.items() if k != "unlabeled") for c in per.values()),
            "pool": panel["pool"], "strata": {s: dict(c) | {"_site": rate(c)} for s, c in per.items()},
            "rule": rate(rule)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--index", type=Path, default=Path("backend/data/discovery_index.db"))
    d.add_argument("--sources", type=Path, default=Path("backend/data/discovery_lot_sources.db"))
    d.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    d.add_argument("--out", type=Path, default=PANEL)
    s = sub.add_parser("serve")
    s.add_argument("--panel", type=Path, default=PANEL)
    s.add_argument("--port", type=int, default=8036)
    c = sub.add_parser("score")
    c.add_argument("--panel", type=Path, default=PANEL)
    c.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if a.cmd == "draw":
        print(json.dumps(draw(a.index, a.sources, a.ptaxsim, a.out), indent=1))
    elif a.cmd == "serve":
        serve(a.panel, a.port)
    else:
        res = score(a.panel)
        if a.out:
            a.out.write_text(json.dumps(res, indent=1) + "\n")
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
