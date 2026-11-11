"""M4 (Phase 7): the labeled panel for "built vs allowed" (decision Item 107).

Item 75's gate for capacity: zero false "underused" on a labeled panel. This script draws that panel and assembles
the independent evidence a person labels it from. No model calls; read-only over local copies.

    PYTHONPATH=. python -m eval.capacity_label_panel draw --permits <permits.json> --out eval/capacity_label_panel.json
    PYTHONPATH=. python -m eval.capacity_label_panel evidence --panel eval/capacity_label_panel.json \
        --permits <permits.json> --lidar <county_buildings_2022.db> --out <evidence.json>

``permits.json`` is the City's building permits (``ydr8-5enu``) since 2015: new construction, demolition, and
renovations of $250,000 or more, with no contact fields (the dataset names real people; they never enter the repo).

**Draw.** 240 base lots in 14 strata, each lot in the first stratum it matches (so a lot is counted once), seeded.
Within a stratum about two thirds are lots the candidate rule calls "underused" where the stratum has enough of them,
because the gate tests exactly that call. The candidate rule (owner-approved for the panel, 2026-11-11): built under
25% of the base district's FAR x lot area, with at least 2,500 sq ft of room, not a narrow strip.

**Evidence** per lot, none of it the figure under test: the lot's outline (ptaxsim), the base district by area
overlap (the City's zoning layer), the City's 2015 footprints inside it with their stories, the County's 2022 LiDAR
outlines over it (area on the lot and height; stories from Item 105's fit), the City's permits on it (by PIN or point),
and link-outs: Street View, the Assessor's page.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

INDEX = Path("backend/data/discovery_index.db")
LOT_SOURCES = Path("backend/data/discovery_lot_sources.db")
PTAXSIM = Path("backend/data/ptaxsim.db")
ZONING = Path("backend/data/map_sources/zoning_layer1.geojson")

SEED = 107
UNDER_SHARE = 0.25
UNDER_ROOM = 2_500.0
UNDER_SHARE_ALT = 1 / 3  # the looser rule, measured on the same labels

# (stratum, size), in the order a lot is assigned.
STRATA: tuple[tuple[str, int], ...] = (
    ("planned_development", 10),
    ("narrow_strip", 10),
    ("condo_building", 10),
    ("complex_member", 20),
    ("recently_built", 20),
    ("demolition_permit", 10),
    ("exempt", 20),
    ("vacant_class_with_building", 15),
    ("vacant_lot", 15),
    ("footprint_area", 20),
    ("district_boundary", 10),
    ("multi_family", 20),
    ("commercial_own_building", 25),
    ("house_assessor", 35),
)
UNDER_SHARE_OF_STRATUM = 2 / 3
NEW_SINCE = "2021-01-01"  # a new-construction permit since then marks "recently built" (records may lag)


def pin10_digits(pin: str) -> str:
    return re.sub(r"\D", "", pin)[:10]


def built_share(a: dict[str, Any]) -> float | None:
    """Built ÷ allowed from the index's own figures (what Discovery shows), None when it can't be said."""
    far, land, bldg = a.get("density_band"), a.get("land_sqft"), a.get("bldg_sqft")
    if a.get("is_vacant") and bldg is None:
        bldg = 0.0
    if a.get("room_scope") == "complex" or not far or not land or land <= 0 or bldg is None:
        return None
    return bldg / (far * land)


def rule_underused(a: dict[str, Any], share_cut: float = UNDER_SHARE) -> bool:
    """The candidate rule. A complex member is judged by its site's room (its own share isn't defined)."""
    if a.get("narrow_strip") or a.get("room_sqft") is None:
        return False
    if a.get("room_scope") == "complex":
        return False  # site-level; labeled, but the rule under test doesn't call members
    share = built_share(a)
    return share is not None and share < share_cut and a["room_sqft"] >= UNDER_ROOM


def load_permits(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text())
    for r in rows:
        r["pins10"] = sorted({p[:10] for p in re.findall(r"\d{10,14}", r.get("pin_list") or "")})
    return rows


def permits_by_pin10(permits: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in permits:
        for p in r["pins10"]:
            out[p].append(r)
    return out


def stratum_of(pin: str, a: dict[str, Any], *, new_pins: set[str], wreck_pins: set[str]) -> str | None:
    p10 = pin10_digits(pin)
    cls = str(a.get("class") or "")
    use = a.get("land_use_class")
    if a.get("room_scope") == "own_rules":
        return "planned_development"
    if a.get("narrow_strip"):
        return "narrow_strip"
    if a.get("room_scope") == "complex":
        return "complex_member"
    if p10 in new_pins or (a.get("year_built") or 0) >= 2018:
        return "recently_built"
    if a.get("warn_demolition") or p10 in wreck_pins:
        return "demolition_permit"
    if cls.startswith("EX"):
        return "exempt"
    if a.get("is_vacant") and a.get("bldg_sqft"):
        return "vacant_class_with_building"
    if a.get("is_vacant"):
        return "vacant_lot"
    if a.get("bldg_sqft_source") == "footprint":
        return "footprint_area"
    if use == "multi_family":
        return "multi_family"
    if use == "commercial" and a.get("bldg_sqft_source") == "commercial_valuation":
        return "commercial_own_building"
    if use == "residential" and a.get("bldg_sqft_source") == "assessor":
        return "house_assessor"
    return None


def _zoning_index():
    import shapely
    from shapely.strtree import STRtree

    feats = json.loads(ZONING.read_text())["features"]
    geoms, classes = [], []
    for f in feats:
        g = shapely.geometry.shape(f["geometry"])
        if not g.is_valid:
            g = shapely.make_valid(g)
        geoms.append(g)
        classes.append(f["properties"].get("ZONE_CLASS"))
    return STRtree(geoms), geoms, classes


def district_shares(lot, ztree) -> list[tuple[str, float]]:
    tree, geoms, classes = ztree
    shares: dict[str, float] = defaultdict(float)
    for i in tree.query(lot, predicate="intersects"):
        inter = lot.intersection(geoms[i]).area
        if inter > 0 and classes[i]:
            shares[classes[i]] += inter / lot.area
    return sorted(shares.items(), key=lambda kv: -kv[1])


def _polygonal(g):
    """The polygon part of a geometry, repaired; None when there is none (a degenerate outline)."""
    import shapely

    if not g.is_valid:
        g = shapely.make_valid(g)
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g if g.area > 0 else None
    parts = [q for q in getattr(g, "geoms", []) if q.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else None


def lot_geometries(pin10s: list[str]) -> dict[str, Any]:
    from shapely import wkt as shapely_wkt

    out: dict[str, Any] = {}
    db = sqlite3.connect(f"file:{PTAXSIM}?mode=ro", uri=True)
    try:
        for i in range(0, len(pin10s), 500):
            chunk = pin10s[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for p, text in db.execute(
                f"SELECT pin10, geometry FROM pin_geometry_raw WHERE pin10 IN ({marks}) AND geometry IS NOT NULL "
                "ORDER BY end_year ASC", chunk,
            ):
                g = _polygonal(shapely_wkt.loads(text))
                if g is not None:
                    out[p] = g
    finally:
        db.close()
    return out


def lot_row(pin: str, a: dict[str, Any], lat: float, lon: float, stratum: str) -> dict[str, Any]:
    share = built_share(a)
    return {
        "pin": pin, "stratum": stratum, "address": a.get("address"), "lat": lat, "lon": lon,
        "hood": a.get("hood"), "class": a.get("class"), "land_use": a.get("land_use_class"),
        "zoning_group": a.get("zoning_group"), "zone_class": a.get("zone_class"),
        "far": a.get("density_band"), "land_sqft": a.get("land_sqft"), "bldg_sqft": a.get("bldg_sqft"),
        "bldg_sqft_source": a.get("bldg_sqft_source"), "year_built": a.get("year_built"),
        "room_sqft": a.get("room_sqft"), "room_scope": a.get("room_scope"),
        "complex_lots": a.get("complex_lots"), "is_vacant": a.get("is_vacant"),
        "narrow_strip": a.get("narrow_strip"), "lot_width_ft": a.get("lot_width_ft"),
        "share": round(share, 4) if share is not None else None,
        "rule_underused": rule_underused(a), "rule_underused_alt": rule_underused(a, UNDER_SHARE_ALT),
    }


def draw(permits_path: Path, out: Path, seed: int = SEED) -> list[dict[str, Any]]:
    permits = load_permits(permits_path)
    new_pins = {p for r in permits if r["permit_type"] == "PERMIT - NEW CONSTRUCTION"
                and (r.get("issue_date") or "") >= NEW_SINCE for p in r["pins10"]}
    wreck_pins = {p for r in permits if r["permit_type"] == "PERMIT - WRECKING/DEMOLITION"
                  and (r.get("issue_date") or "") >= "2023-01-01" for p in r["pins10"]}

    db = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    pools: dict[str, list[tuple[str, dict, float, float]]] = defaultdict(list)
    condo: dict[str, tuple[str, dict, float, float]] = {}
    for pin, lat, lon, attrs in db.execute("SELECT pin, lat, lon, attrs FROM parcels ORDER BY pin"):
        a = json.loads(attrs)
        if not pin.endswith("-0000"):
            if a.get("class") in ("2-99", "5-99"):
                condo.setdefault(pin[:13], (pin, a, lat, lon))
            continue
        s = stratum_of(pin, a, new_pins=new_pins, wreck_pins=wreck_pins)
        if s:
            pools[s].append((pin, a, lat, lon))
    db.close()
    pools["condo_building"] = list(condo.values())

    rng = random.Random(seed)
    # District boundary: lots whose leading district covers under 90% (by area), found in a random sample.
    boundary_pool = [r for s in ("house_assessor", "commercial_own_building", "multi_family") for r in pools[s]]
    sample = rng.sample(boundary_pool, 6000)
    geoms = lot_geometries([pin10_digits(r[0]) for r in sample])
    ztree = _zoning_index()
    for r in sample:
        g = geoms.get(pin10_digits(r[0]))
        if g is None or g.area <= 0:
            continue
        sh = district_shares(g, ztree)
        if sh and sh[0][1] < 0.9 and len(sh) > 1:
            pools["district_boundary"].append(r)

    taken: set[str] = set()
    panel: list[dict[str, Any]] = []
    for stratum, size in STRATA:
        pool = [r for r in pools[stratum] if r[0] not in taken]
        under = [r for r in pool if rule_underused(r[1])]
        other = [r for r in pool if not rule_underused(r[1])]
        n_under = min(len(under), round(size * UNDER_SHARE_OF_STRATUM))
        pick = rng.sample(under, n_under) + rng.sample(other, min(len(other), size - n_under))
        for pin, a, lat, lon in pick:
            taken.add(pin)
            panel.append(lot_row(pin, a, lat, lon, stratum) | {"pool": len(pools[stratum]), "pool_underused": len(under)})
    out.write_text(json.dumps({"seed": seed, "rule": {"share_under": UNDER_SHARE, "room_at_least": UNDER_ROOM},
                               "strata": dict(STRATA), "lots": panel}, indent=1))
    return panel


def _rings(g) -> list[list[list[float]]]:
    """Exterior rings of a geometry's polygons as [lon, lat] lists (for drawing; holes left out)."""
    polys = [g] if g.geom_type == "Polygon" else [q for q in getattr(g, "geoms", []) if q.geom_type == "Polygon"]
    if g.geom_type == "MultiPolygon":
        polys = list(g.geoms)
    return [[[round(x, 6), round(y, 6)] for x, y in q.exterior.coords] for q in polys]


def stories_from_height(h: float) -> int:
    """Item 105's fit (half the footprints fitted, half tested): 79.9% exact against the City's stories."""
    s = round((h - 3) / 14.75) if h < 40 else round(h / 14)
    return max(1, int(s))


# Stories a permit states ("ERECT 4 STORY 6 D.U. BUILDING"). The owner trusts a permit's stories over LiDAR's
# estimate from height (2026-11-11): a 4-story permit read 5 from LiDAR.
_WORD_N = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10}
_STORIES_RE = re.compile(r"\b(\d{1,2}|" + "|".join(_WORD_N) + r")[\s-]*(?:STORY|STORIES|STOREY|STY)\b", re.I)


def permit_stories(description: str) -> int | None:
    m = _STORIES_RE.search(description or "")
    if not m:
        return None
    v = m.group(1).upper()
    n = _WORD_N.get(v) or int(v)
    return n if 1 <= n <= 60 else None


# LiDAR parts that aren't this lot's building (owner, 2026-11-11, and his batch-1 labels: the parts he set to 0
# stories were mostly under 10% of their outline on the lot). A tiny part is a tree, an AC unit or a misdraw.
TREE_MAX_SQFT = 150
NEIGHBOR_EDGE_SHARE = 0.10
NEIGHBOR_EDGE_MAX_SQFT = 400


def ignore_reason(on_lot: float, outline: float) -> str | None:
    if on_lot < TREE_MAX_SQFT:
        return "too_small"
    if outline > 0 and on_lot / outline < NEIGHBOR_EDGE_SHARE and on_lot < NEIGHBOR_EDGE_MAX_SQFT:
        return "neighbor_edge"
    return None


# Street View: Google opens the panorama nearest the point it's sent, and a lot's middle is often nearer the alley.
# Stand on the address's own street (else the nearest named street) and face the lot: the app's rule
# (frontend/src/ui-next/map/streetView.ts, Item 94), here in Python for the labeling page.
ROADS_DATASET = "pr57-gg9e"
SNAP_MAX_M = 60.0
_KX = 111_320 * 0.7450  # metres per degree of longitude at 41.84° N
_KY = 110_540


def _metric(g):
    import shapely
    return shapely.transform(g, lambda xy: xy * [_KX, _KY])


def load_roads(cache: Path) -> list[tuple[str, Any]]:
    """[(lower-case sign-style name, line in metres)]; fetched once from the City (no app token needed) and cached."""
    import shapely
    from shapely.geometry import shape

    from backend.map_tiles.base_tiles import ROAD_CLASSES, _fetch, street_name

    if cache.exists():
        rows = json.loads(cache.read_text())
    else:
        rows = _fetch(ROADS_DATASET, "the_geom,class,status,pre_dir,street_nam,street_typ")
        cache.write_text(json.dumps(rows))
    out = []
    for r in rows:
        kind = ROAD_CLASSES.get(str(r.get("class", "")).strip(), (None, 0))[0]
        if kind in (None, "ramp", "highway") or not r.get("the_geom"):
            continue
        name = street_name(r.get("pre_dir"), r.get("street_nam"), r.get("street_typ")).lower()
        if name:
            out.append((name, _metric(shapely.make_valid(shape(r["the_geom"])))))
    return out


def street_of_address(address: str | None) -> str | None:
    if not address:
        return None
    s = re.sub(r"^~", "", address).strip()
    s = re.sub(r"\b(unit|apt|#|ste|suite)\b.*$", "", s, flags=re.I)
    s = re.sub(r"^\d+[A-Z]?(-\d+[A-Z]?)?\s+", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s or None


def street_viewpoint(lot, address: str | None, roads: list[tuple[str, Any]], tree) -> tuple[float, float, int | None]:
    """(lat, lon, heading): the nearest spot on the address's street within 60 m, else on the nearest named street;
    the heading faces the lot. The lot's own interior point (no heading) when no street is near."""
    import math

    from shapely.ops import nearest_points

    rep = lot.representative_point()
    target = _metric(rep)
    want = street_of_address(address)
    near = [roads[i] for i in tree.query(target.buffer(SNAP_MAX_M))]
    pool = [g for n, g in near if n == want] or [g for _, g in near]
    best = min(((g.distance(target), g) for g in pool), default=None, key=lambda t: t[0])
    if best is None or best[0] > SNAP_MAX_M:
        return rep.y, rep.x, None
    pt = nearest_points(best[1], target)[0]
    heading = round((math.degrees(math.atan2(target.x - pt.x, target.y - pt.y)) + 360) % 360)
    return pt.y / _KY, pt.x / _KX, heading


def evidence(panel_path: Path, permits_path: Path, lidar_path: Path, out: Path) -> list[dict[str, Any]]:
    rows = evidence_rows(json.loads(panel_path.read_text())["lots"], permits_path, lidar_path)
    out.write_text(json.dumps(rows, indent=1))
    return rows


def evidence_rows(panel: list[dict[str, Any]], permits_path: Path, lidar_path: Path,
                  roads_cache: Path | None = None) -> list[dict[str, Any]]:
    import shapely
    from shapely.strtree import STRtree

    from backend.discovery.lot_facts import LotSources
    from backend.discovery.lot_sources import area_sqft
    from backend.retrieval.zoning_definitions import get_zone_definition

    permits = load_permits(permits_path)
    by_pin = permits_by_pin10(permits)
    p_pts = [(shapely.Point(float(r["longitude"]), float(r["latitude"])), r) for r in permits
             if r.get("latitude") and r.get("longitude")]
    p_tree = STRtree([p for p, _ in p_pts])
    geoms = lot_geometries([pin10_digits(r["pin"]) for r in panel])
    src = LotSources.load(LOT_SOURCES)
    ztree = _zoning_index()

    # The County's LiDAR outlines near any panel lot (the file has no spatial index: one pass, keep the near ones).
    hull = shapely.union_all([g.envelope.buffer(0.0005) for g in geoms.values()])
    ld = sqlite3.connect(f"file:{lidar_path}?mode=ro", uri=True)
    l_geoms, l_h = [], []
    for oid, h, wkb in ld.execute("SELECT oid, height_ft, wkb FROM buildings"):
        g = shapely.from_wkb(wkb)
        if hull.intersects(g):
            l_geoms.append(g if g.is_valid else shapely.make_valid(g))
            l_h.append((oid, h))
    ld.close()
    l_tree = STRtree(l_geoms)
    roads = load_roads(roads_cache or lidar_path.with_name("roads_pr57-gg9e.json"))
    r_tree = STRtree([g for _, g in roads])

    rows = []
    for lot in panel:
        p10 = pin10_digits(lot["pin"])
        g = geoms.get(p10)
        ev: dict[str, Any] = {"pin": lot["pin"]}
        if g is None:
            ev["missing"] = "no lot outline in ptaxsim"
            rows.append(ev)
            continue
        rep = g.representative_point()
        ev["lot_sqft_outline"] = round(area_sqft(g))
        ev["outline"] = _rings(g)
        sh = district_shares(g, ztree)
        ev["districts"] = [{"zone": z, "share": round(s, 3), "far": get_zone_definition(z).far} for z, s in sh[:3]]
        # City footprints whose interior point is inside the lot (the rule Discovery's fill uses).
        fps = []
        for i in src.fp_tree.query(g, predicate="contains"):
            fps.append({"area_sqft": round(src.fp_area[i]), "stories": src.fp_stories[i],
                        "rings": _rings(src.fp_geoms[i])})
        ev["city_footprints_2015"] = fps
        # County LiDAR outlines over the lot: the part on the lot, its height and stories by Item 105's fit.
        lid = []
        for i in l_tree.query(g, predicate="intersects"):
            on = g.intersection(l_geoms[i])
            on_sqft = area_sqft(on)
            if on_sqft < 50:
                continue
            oid, h = l_h[i]
            outline_sqft = area_sqft(l_geoms[i])
            lid.append({"oid": oid, "on_lot_sqft": round(on_sqft), "outline_sqft": round(outline_sqft),
                        "height_ft": round(h, 1), "stories_est": stories_from_height(h),
                        "ignore": ignore_reason(on_sqft, outline_sqft), "rings": _rings(on)})
        lid.sort(key=lambda x: -x["on_lot_sqft"])
        ev["lidar_2022"] = lid
        # Permits on the lot: by PIN, else by point inside the lot (3 m slack).
        seen, plist = set(), []
        cands = list(by_pin.get(p10, []))
        cands += [p_pts[i][1] for i in p_tree.query(g.buffer(0.00003), predicate="contains")]
        for r in cands:
            if r["permit_"] in seen:
                continue
            seen.add(r["permit_"])
            plist.append({
                "type": re.sub(r"^PERMIT\s*[-–]\s*", "", r["permit_type"]), "date": (r.get("issue_date") or "")[:10],
                "cost": float(r["reported_cost"]) if r.get("reported_cost") else None,
                "address": " ".join(x for x in (r.get("street_number"), r.get("street_direction"), r.get("street_name")) if x),
                "description": (r.get("work_description") or "")[:240],
            })
        for q in plist:
            q["stories"] = permit_stories(q["description"]) if q["type"] == "NEW CONSTRUCTION" else None
        ev["permits"] = sorted(plist, key=lambda x: x["date"], reverse=True)
        # The newest new-construction permit that states stories, issued before the LiDAR flight (a later building
        # isn't in the LiDAR at all): its stories replace LiDAR's estimate on the lot's largest building.
        stated = [q for q in ev["permits"] if q["stories"] and q["date"] < LIDAR_FLOWN]
        ev["permit_stories"] = {"stories": stated[0]["stories"], "date": stated[0]["date"]} if stated else None
        main = next((x for x in lid if not x["ignore"]), None)
        if main and stated:
            main["stories_permit"] = stated[0]["stories"]
        kept = [x for x in lid if not x["ignore"]]
        ev["lidar_floor_area_est"] = round(sum(x["on_lot_sqft"] * x.get("stories_permit", x["stories_est"]) for x in kept))
        ev["lidar_floor_area_raw"] = round(sum(x["on_lot_sqft"] * x["stories_est"] for x in lid))
        ev["lidar_coverage"] = round(sum(x["on_lot_sqft"] for x in kept) / max(1, ev["lot_sqft_outline"]), 3)
        lat, lon, heading = street_viewpoint(g, lot.get("address"), roads, r_tree)
        ev["street_view"] = (f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lon:.6f}"
                             + (f"&heading={heading}" if heading is not None else ""))
        ev["street_view_snapped"] = heading is not None
        ev["map_link"] = f"https://www.google.com/maps/search/?api=1&query={rep.y:.6f},{rep.x:.6f}"
        ev["assessor"] = f"https://www.cookcountyassessor.com/pin/{re.sub(r'[^0-9]', '', lot['pin'])}"
        rows.append(ev)
    return rows


# ── Rule v2 (after the owner's first 64 labels, 2026-11-11) ──────────────────────────────────────────────────────
# The 64 labels showed the record's building area alone is not enough: six of eight false calls were apartment or
# commercial buildings recorded at 4-23% of allowed that stand at 33-116%. v2 calls "underused" only when two
# independent measures agree (the record and the County's 2022 LiDAR volume), and nothing has been built or torn down
# since the LiDAR flight. A lot with no building in the records and none in the LiDAR is "empty", a separate state:
# the owner's side-yard cases (a vacant lot used with the house next door) are empty but not an open opportunity.
LIDAR_FLOWN = "2022-04-01"
LIDAR_MIN_PART = 150  # sq ft of a LiDAR outline on the lot before it counts as a building there
CROSSING_SHARE = 0.8  # an outline of 1,000+ sq ft with under 80% of it on the lot crosses the lot line
BIG_PERMIT = 100_000  # a new-construction permit this size or more (or of unknown cost) is a building


def rule_v2(lot: dict[str, Any], ev: dict[str, Any]) -> tuple[str, str]:
    """("underused" | "empty" | "none", why). Conservative: anything uncertain is "none" (the app says nothing)."""
    if lot.get("room_scope") == "complex" or lot.get("stratum") == "condo_building":
        return "none", "part of a complex or condo"
    if not lot.get("far"):
        return "none", "no base FAR"
    if lot.get("narrow_strip"):
        return "none", "narrow strip"
    land = lot.get("land_sqft")
    if not land or "missing" in ev:
        return "none", "no lot area or outline"
    allowed = lot["far"] * land
    after = [q for q in ev.get("permits", []) if q["date"] >= LIDAR_FLOWN]
    if any(q["type"] == "NEW CONSTRUCTION" and (q["cost"] is None or q["cost"] >= BIG_PERMIT) for q in after):
        return "none", "new building since the LiDAR"
    if any(q["type"] == "WRECKING/DEMOLITION" for q in after):
        return "none", "demolition since the LiDAR"
    parts = [x for x in ev.get("lidar_2022", []) if not x.get("ignore") and x["on_lot_sqft"] >= LIDAR_MIN_PART]
    if any(x["outline_sqft"] >= 1000 and x["on_lot_sqft"] < CROSSING_SHARE * x["outline_sqft"] for x in parts):
        return "none", "a building crosses the lot line"
    rec = lot.get("bldg_sqft") or 0.0
    if not parts:
        return ("empty", "no building on record or in the LiDAR") if rec == 0 else ("none", "record building, none in LiDAR")
    lid = ev.get("lidar_floor_area_est") or 0.0
    if rec / allowed < UNDER_SHARE and lid / allowed < UNDER_SHARE and allowed - max(rec, lid) >= UNDER_ROOM:
        return "underused", "record and LiDAR both under 25%"
    return "none", "built"


# Batch 2: lots drawn so that v2's calls can be measured (batch 1 has only 15 of them).
BATCH2_SEED = 1072
BATCH2_CANDIDATES = {"house_assessor": 900, "commercial_own_building": 350, "multi_family": 250, "exempt": 200,
                     "footprint_area": 200, "vacant_class_with_building": 120, "recently_built": 120,
                     "demolition_permit": 100, "vacant_lot": 120}
BATCH2_UNDER = {"house_assessor": 35, "commercial_own_building": 25, "multi_family": 10, "exempt": 10,
                "footprint_area": 10, "vacant_class_with_building": 5, "recently_built": 5, "demolition_permit": 5}
BATCH2_EMPTY = {"vacant_lot": 25, "exempt": 10, "vacant_class_with_building": 5}
BATCH2_CONTROLS = 15  # v2 says "none" though the record alone says underused: keeps the batch blind


def draw2(permits_path: Path, lidar_path: Path, out: Path, ev_out: Path, exclude: Path) -> list[dict[str, Any]]:
    permits = load_permits(permits_path)
    new_pins = {p for r in permits if r["permit_type"] == "PERMIT - NEW CONSTRUCTION"
                and (r.get("issue_date") or "") >= NEW_SINCE for p in r["pins10"]}
    wreck_pins = {p for r in permits if r["permit_type"] == "PERMIT - WRECKING/DEMOLITION"
                  and (r.get("issue_date") or "") >= "2023-01-01" for p in r["pins10"]}
    taken = {r["pin"] for r in json.loads(exclude.read_text())["lots"]}
    db = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    pools: dict[str, list[tuple[str, dict, float, float]]] = defaultdict(list)
    for pin, lat, lon, attrs in db.execute("SELECT pin, lat, lon, attrs FROM parcels ORDER BY pin"):
        if not pin.endswith("-0000") or pin in taken:
            continue
        a = json.loads(attrs)
        s = stratum_of(pin, a, new_pins=new_pins, wreck_pins=wreck_pins)
        if s not in BATCH2_CANDIDATES:
            continue
        if s == "vacant_lot" or rule_underused(a) or (s in BATCH2_EMPTY and a.get("is_vacant") or
                                                       (s == "exempt" and a.get("bldg_sqft") == 0)):
            pools[s].append((pin, a, lat, lon))
    db.close()
    rng = random.Random(BATCH2_SEED)
    cands = []
    for s, n in BATCH2_CANDIDATES.items():
        for pin, a, lat, lon in rng.sample(pools[s], min(n, len(pools[s]))):
            cands.append(lot_row(pin, a, lat, lon, s) | {"pool": len(pools[s])})
    evs = {e["pin"]: e for e in evidence_rows(cands, permits_path, lidar_path)}
    for c in cands:
        c["v2"], c["v2_why"] = rule_v2(c, evs[c["pin"]])
    pick: list[dict[str, Any]] = []
    for s, n in BATCH2_UNDER.items():
        pick += [c for c in cands if c["stratum"] == s and c["v2"] == "underused"][:n]
    for s, n in BATCH2_EMPTY.items():
        pick += [c for c in cands if c["stratum"] == s and c["v2"] == "empty"][:n]
    controls = [c for c in cands if c["v2"] == "none" and c["rule_underused"]]
    pick += rng.sample(controls, min(BATCH2_CONTROLS, len(controls)))
    for c in pick:
        c["batch"] = 2
    tally: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in cands:
        tally[c["stratum"]][c["v2"]] += 1
    out.write_text(json.dumps({"seed": BATCH2_SEED, "rule": "v2", "candidates": {k: dict(v) for k, v in tally.items()},
                               "lots": pick}, indent=1))
    ev_out.write_text(json.dumps([evs[c["pin"]] for c in pick], indent=1))
    return pick


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--permits", type=Path, required=True)
    d.add_argument("--out", type=Path, default=Path("eval/capacity_label_panel.json"))
    e = sub.add_parser("evidence")
    e.add_argument("--panel", type=Path, default=Path("eval/capacity_label_panel.json"))
    e.add_argument("--permits", type=Path, required=True)
    e.add_argument("--lidar", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    d2 = sub.add_parser("draw2")
    d2.add_argument("--permits", type=Path, required=True)
    d2.add_argument("--lidar", type=Path, required=True)
    d2.add_argument("--exclude", type=Path, default=Path("eval/capacity_label_panel.json"))
    d2.add_argument("--out", type=Path, default=Path("eval/capacity_label_panel_2.json"))
    d2.add_argument("--evidence-out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "draw2":
        pick = draw2(args.permits, args.lidar, args.out, args.evidence_out, args.exclude)
        by = defaultdict(lambda: defaultdict(int))
        for r in pick:
            by[r["stratum"]][r["v2"]] += 1
        for s, c in by.items():
            print(f"{s:28} {dict(c)}")
        print(f"total {len(pick)}")
        return 0
    if args.cmd == "draw":
        panel = draw(args.permits, args.out)
        by = defaultdict(lambda: [0, 0])
        for r in panel:
            by[r["stratum"]][0] += 1
            by[r["stratum"]][1] += r["rule_underused"]
        for s, (n, u) in by.items():
            print(f"{s:28} {n:4} lots, {u:3} underused by the rule")
        print(f"total {len(panel)}, underused {sum(r['rule_underused'] for r in panel)}")
    else:
        rows = evidence(args.panel, args.permits, args.lidar, args.out)
        print(f"{len(rows)} lots, {sum('missing' in r for r in rows)} without an outline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
