"""Where the lot map disagrees with the base map (decision Item 128, the owner's map review of 2026-11-16).

Read-only over local copies, no model calls. For every base lot of a Discovery index, against its newest PTAXSIM
outline:

* the share of the lot under a Chicago Park District park (``ejsh-fztr``) and under the City's water (``knfe-65pw``),
  both from the base map's own source copies (``map_sources/``);
* CMAP 2023's main code and share (``cmap_on_lot`` in ``discovery_lot_sources.db``);
* the feet of each drawn rail line inside the lot (``backend.map_tiles.rail_lines``);
* what the map shows today: the room band (``r``) and the land-in-use band (``l``) from ``lot_facts.measure_bands``.

It then sorts the disagreements into findings, each with counts and the largest examples, so a fix is measured on the
whole city and not only on the spots someone happened to look at:

* ``unknown_*``: lots drawn "not known" (no room band) that a park, cemetery, water or rail source covers;
* ``room_on_*``: lots that show room to build although a park, cemetery or water covers most of them;
* ``line_through_unmarked``: lots a drawn active rail line crosses for 25 ft or more that are not rail land, by what
  the lot is;
* ``lots_over_water``: lot outlines mostly inside the City's water polygons.

    PYTHONPATH=. python -m eval.map_audit --index <discovery_index.db> --sources <discovery_lot_sources.db> \\
        --map-sources <map_sources/> [--ptaxsim backend/data/ptaxsim.db] [--out <dir>] [--lots-out <lots.json>]
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from backend.discovery.cmap_land_use import pair_shares
from backend.map_tiles import rail_lines

HALF = 0.5
LINE_MIN_FT = 25.0
CEMETERY = "1360"
CMAP_NAMES = {"1511": "rail", "1570": "rail_yard", "1512": "road", "1520": "other_linear", "1360": "cemetery",
              "3100": "open_space", "3200": "open_space", "3300": "open_space", "3400": "open_space",
              "3500": "open_space", "5000": "water", "1540": "parking"}


def _polys(path: Path) -> np.ndarray:
    from backend.map_tiles.base_tiles import is_island

    out = []
    for r in json.loads(path.read_text()):
        if r.get("the_geom") and not is_island(r):
            g = shape(r["the_geom"])
            out.append(g if g.is_valid else shapely.make_valid(g))
    return np.array(out, dtype=object)


def _share_by_lot(lots: np.ndarray, polys: np.ndarray) -> dict[int, float]:
    acc: dict[int, float] = collections.defaultdict(float)
    for li, _gi, sh in zip(*pair_shares(lots, STRtree(polys), polys)):
        acc[int(li)] += float(sh)
    return {k: min(v, 1.0) for k, v in acc.items()}


def measure(index: Path, sources: Path, map_sources: Path, ptaxsim: Path) -> list[dict]:
    from backend.discovery.index_backfill import lot_outlines
    from backend.discovery.lot_facts import measure_bands

    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    rows = db.execute("SELECT pin, lat, lon, attrs FROM parcels WHERE pin LIKE '%0000'").fetchall()
    db.close()
    src = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    cmap = {r[0]: (r[1], r[2]) for r in src.execute("SELECT pin10, code, share FROM cmap_on_lot")}
    src.close()
    outlines = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in rows})
    recs, geo, idx = [], [], []
    for pin, lat, lon, attrs in rows:
        a = json.loads(attrs)
        p10 = pin.replace("-", "")[:10]
        b = measure_bands(a)
        c = cmap.get(p10)
        rec = {"pin": pin, "lat": lat, "lon": lon, "address": a.get("address"), "class": a.get("class"),
               "land_kind": a.get("land_kind"), "structure": a.get("structure"), "zone": a.get("zone_class"),
               "zoning_group": a.get("zoning_group"), "infrastructure": a.get("infrastructure"),
               "unusual": bool(a.get("unusual")), "room_sqft": a.get("room_sqft"), "room_scope": a.get("room_scope"),
               "bldg_sqft_unknown": a.get("bldg_sqft_unknown"), "land_sqft": a.get("land_sqft"),
               "r": b.get("r"), "l": b.get("l"),
               "cmap": c[0] if c else None, "cmap_share": c[1] if c else 0.0}
        g = outlines.get(p10)
        if g is not None and g.area > 0:
            idx.append(len(recs))
            geo.append(g)
        recs.append(rec)
    lots = np.array(geo, dtype=object)
    for name, polys in (("park", _polys(map_sources / "ejsh-fztr.json")),
                        ("water", _polys(map_sources / "knfe-65pw.json"))):
        for li, sh in _share_by_lot(lots, polys).items():
            recs[idx[li]][f"{name}_share"] = round(sh, 3)
    lines = rail_lines.load(map_sources)
    lots_ft = np.array([rail_lines.to_feet(g) for g in geo], dtype=object)
    tree = STRtree(lots_ft)
    for kind in ("cta", "cta_subway", "metra", "amtrak", "freight", "yard", "spur"):
        gs = np.array([rail_lines.to_feet(g) for k, g, _ in lines if k == kind], dtype=object)
        if not len(gs):
            continue
        li, gi = tree.query(gs, predicate="intersects")[::-1]
        acc: dict[int, float] = collections.defaultdict(float)
        for a_, b_ in zip(li, gi):
            acc[int(a_)] += float(lots_ft[a_].intersection(gs[b_]).length)
        for a_, ft in acc.items():
            if ft > 0:
                recs[idx[a_]][f"{kind}_ft"] = round(ft, 1)
    return recs


ACTIVE = ("cta", "metra", "amtrak", "freight", "yard")


def _line_ft(r: dict) -> float:
    return sum(r.get(f"{k}_ft", 0.0) for k in ACTIVE)


def _ex(rs: list[dict], n: int = 8) -> list[dict]:
    rs = sorted(rs, key=lambda r: -(r.get("land_sqft") or 0))
    return [{k: r.get(k) for k in ("pin", "address", "class", "land_kind", "structure", "cmap", "cmap_share", "r",
                                   "zone", "park_share", "water_share", "land_sqft")} for r in rs[:n]]


def summarize(recs: list[dict]) -> dict:
    C = collections.Counter
    out: dict = {"lots": len(recs), "room_band": dict(C(r["r"] or "none" for r in recs).most_common())}
    unk = [r for r in recs if r["r"] is None]
    out["unknown"] = {"lots": len(unk), "why_no_room": dict(C(r.get("bldg_sqft_unknown") or "other" for r in unk)
                                                            .most_common(8)),
                      "by_class": dict(C(str(r["class"])[:2] for r in unk).most_common(10))}

    def finding(name: str, rs: list[dict]) -> None:
        out[name] = {"lots": len(rs), "shown": sum(not r["unusual"] for r in rs),
                     "by_class": dict(C(str(r["class"])[:2] for r in rs).most_common(6)),
                     "by_zoning": dict(C(r.get("zoning_group") or "none" for r in rs).most_common(6)),
                     "examples": _ex(rs)}

    park = lambda r: r.get("park_share", 0) >= HALF  # noqa: E731
    cem = lambda r: r["cmap"] == CEMETERY and r["cmap_share"] >= HALF  # noqa: E731
    water = lambda r: r.get("water_share", 0) >= HALF  # noqa: E731
    finding("unknown_park", [r for r in unk if park(r)])
    finding("unknown_cemetery", [r for r in unk if cem(r)])
    finding("unknown_water", [r for r in unk if water(r)])
    finding("unknown_cmap_open_space", [r for r in unk if CMAP_NAMES.get(r["cmap"]) == "open_space"
                                        and r["cmap_share"] >= HALF and not park(r)])
    finding("room_on_park", [r for r in recs if r["r"] not in (None, "p", "t", "x") and park(r)])
    finding("room_on_cemetery", [r for r in recs if r["r"] not in (None, "p", "t", "x") and cem(r)])
    finding("lots_over_water", [r for r in recs if water(r)])
    crossed = [r for r in recs if _line_ft(r) >= LINE_MIN_FT and r.get("infrastructure") not in ("rail", "road_rail")]
    out["line_through_unmarked"] = {
        "lots": len(crossed),
        "by_r": dict(C(r["r"] or "none" for r in crossed).most_common()),
        "by_cmap": dict(C(CMAP_NAMES.get(r["cmap"], r["cmap"]) for r in crossed).most_common(10)),
        "by_class": dict(C(str(r["class"])[:2] for r in crossed).most_common(8)),
        "by_structure": dict(C(r["structure"] or "none" for r in crossed).most_common()),
    }
    finding("line_through_unknown", [r for r in crossed if r["r"] is None])
    finding("line_through_cmap_road_not_marked", [r for r in crossed if r["cmap"] == "1512"
                                                  and r.get("infrastructure") != "road"])
    return out


def _plain(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--index", type=Path)
    ap.add_argument("--sources", type=Path)
    ap.add_argument("--map-sources", type=Path)
    ap.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    ap.add_argument("--out", type=Path, default=Path("eval/results/2026-11-16-map-audit"))
    ap.add_argument("--lots-out", type=Path, default=None)
    ap.add_argument("--from-lots", type=Path, default=None)
    a = ap.parse_args()
    recs = json.loads(a.from_lots.read_text()) if a.from_lots else measure(a.index, a.sources, a.map_sources,
                                                                           a.ptaxsim)
    if a.lots_out and not a.from_lots:
        a.lots_out.write_text(json.dumps(recs, default=_plain))
    s = summarize(recs)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "summary.json").write_text(json.dumps(s, indent=1, default=_plain))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "examples"})
                      for k, v in s.items()}, indent=1, default=_plain))


if __name__ == "__main__":
    main()
