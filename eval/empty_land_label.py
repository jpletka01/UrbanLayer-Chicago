"""Precision check for "physically empty" (decision Item 110): of the lots ``eval.empty_land`` calls empty, how many
are empty when a person looks? No model calls; the page is served on localhost only.

    PYTHONPATH=. python -m eval.empty_land_label draw --lots <empty_lots.json from eval.empty_land --lots-out> \\
        --sources <discovery_lot_sources.db> [--exclude <owner's M4 labels.json>] [--ptaxsim backend/data/ptaxsim.db]
    PYTHONPATH=. python -m eval.empty_land_label serve [--port 8033]
    PYTHONPATH=. python -m eval.empty_land_label score

**Draw** (seeded): 60 lots called empty, by kind of land, so each kind the filter would offer is checked:
vacant class 15, City-owned 10, parking/minor improvement (5-90, 5-80) 10, exempt 10, residential classes 10,
other commercial 5. Lots on the owner's M4 panel are left out.

**Blind.** The page shows the lot's outline, its neighbors with their own City addresses, the street names, the County's
LiDAR buildings AROUND the lot (cut out of the lot itself, for orientation), a Street View link standing on the nearest
street facing the lot, and Google's satellite view; never the footprints, LiDAR or permits on the lot being tested. The labeler
says what is on the lot today: nothing (or paving), only a garage or shed, a building, construction, or can't tell.

Labels are saved as they are made to ``eval/results/2026-11-11-empty-land/labels.json``, which stays out of the repo
(``.gitignore``); ``score`` prints counts only.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

from eval.assessor_address_label import _FT_LAT, _FT_LON, _ring, _viewpoint, _wilson

PANEL = Path("eval/empty_land_panel.json")
PAGE = Path(__file__).with_name("empty_land_label_page.html")
LABELS = Path("eval/results/2026-11-11-empty-land/labels.json")
SEED = 110
STRATA = (("vacant_class", 15), ("city_owned", 10), ("parking", 10), ("exempt", 10), ("residential", 10),
          ("other_commercial", 5))
NEAR_FT = 160.0


def stratum_of(kind: str) -> str | None:
    if kind in ("vacant_class", "city_owned", "exempt", "residential"):
        return kind
    if kind in ("commercial_5-90", "commercial_5-80"):
        return "parking"
    if kind.startswith("commercial"):
        return "other_commercial"
    return None  # railroad, side yards, other: not offered as building sites


def draw(lots_path: Path, sources: Path, ptaxsim: Path, exclude: Path | None, out: Path,
         lidar: Path | None = None, index: Path | None = None) -> dict:
    import numpy as np
    import shapely
    from shapely.strtree import STRtree

    from backend.discovery.index_backfill import lot_outlines

    rows = json.loads(lots_path.read_text())
    skip = set(json.loads(exclude.read_text())) if exclude else set()
    pool: dict[str, list[dict]] = {}
    for r in rows:
        s = stratum_of(r["kind"])
        if r["state"] == "empty" and s and r["pin"] not in skip:
            pool.setdefault(s, []).append(r)
    rnd = random.Random(SEED)
    picked = []
    for s, n in STRATA:
        picked += [dict(r, stratum=s) for r in rnd.sample(pool[s], n)]
    rnd.shuffle(picked)

    # Neighbors: every base lot in the measurement within NEAR_FT; the street: the nearest centerline pieces.
    lat_a = np.array([r["lat"] for r in rows])
    lon_a = np.array([r["lon"] for r in rows])

    def near_idx(r):
        return np.nonzero(np.hypot((lat_a - r["lat"]) * _FT_LAT, (lon_a - r["lon"]) * _FT_LON) <= NEAR_FT)[0]

    db = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    cl = db.execute("SELECT wkb, pre_dir, name, typ FROM centerlines").fetchall()
    db.close()
    lines = shapely.from_wkb([c[0] for c in cl])
    names = [" ".join(x for x in (c[1], c[2], c[3]) if x) for c in cl]
    # For orientation only: buildings AROUND the lot (County 2022 LiDAR), cut out of the lot itself, which is what is
    # being checked; and the neighbors' own City addresses.
    b_geoms, b_tree = None, None
    if lidar:
        ld = sqlite3.connect(f"file:{lidar}?mode=ro", uri=True)
        b_geoms = shapely.from_wkb([r[0] for r in ld.execute("SELECT wkb FROM buildings WHERE height_ft >= 8")])
        ld.close()
        b_tree = STRtree(b_geoms)
    addr: dict[str, str] = {}
    if index:
        ix = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        want = sorted({rows[i]["pin"] for r in picked for i in near_idx(r)})
        for i in range(0, len(want), 900):
            chunk = want[i:i + 900]
            for pin, a in ix.execute(f"SELECT pin, json_extract(attrs, '$.address') FROM parcels WHERE pin IN "
                                     f"({','.join('?' * len(chunk))})", chunk):
                if a and not str(a).startswith("~"):
                    addr[pin] = a
        ix.close()
    tree = STRtree(lines)
    near = {r["pin"]: near_idx(r) for r in picked}
    outlines = lot_outlines(ptaxsim, {rows[i]["pin"].replace("-", "")[:10] for v in near.values() for i in v})
    out_lots = []
    for k, r in enumerate(picked):
        own = outlines.get(r["pin"].replace("-", "")[:10])
        own10 = r["pin"].replace("-", "")[:10]
        nb = []
        for i in near[r["pin"]]:
            pin = rows[i]["pin"]
            p10 = pin.replace("-", "")[:10]
            if p10 in outlines and p10 != own10:
                nb.append({"ring": _ring(outlines[p10]), "address": addr.get(pin)})
        c = shapely.Point(r["lon"], r["lat"])
        idx = tree.query(c.buffer(0.0012), predicate="intersects")  # ~400 ft
        street = [[[round(x, 7), round(y, 7)] for x, y in (g.geoms[0] if g.geom_type == "MultiLineString" else g).coords]
                  for g in (lines[i] for i in idx)]
        street_names = [names[i] for i in idx]
        buildings = []
        if b_tree is not None:
            for i in b_tree.query(c.buffer(0.0007), predicate="intersects"):  # ~250 ft
                g = b_geoms[i] if b_geoms[i].is_valid else shapely.make_valid(b_geoms[i])
                if own is not None:
                    g = g.difference(own.buffer(0.000005))
                for part in getattr(g, "geoms", [g]):
                    if part.geom_type == "Polygon" and not part.is_empty and part.area > 1e-10:
                        buildings.append(_ring(part.simplify(0.000002)))
        out_lots.append({"id": k + 1, "pin": r["pin"], "stratum": r["stratum"], "lat": r["lat"], "lon": r["lon"],
                         "lot_sqft": r.get("lot_sqft"), "ring": _ring(own) if own is not None else None,
                         "neighbors": nb, "street": street, "street_names": street_names, "buildings": buildings,
                         "viewpoint": _viewpoint(street, r["lat"], r["lon"])})
    out.write_text(json.dumps({"seed": SEED, "pool": {s: len(v) for s, v in pool.items()}, "lots": out_lots}, indent=1))
    return {s: len(v) for s, v in pool.items()}


def _read_labels() -> dict:
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}


def _write_labels(labels: dict) -> None:
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=LABELS.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(labels, f, indent=1, sort_keys=True)
    os.replace(tmp, LABELS)


def serve(panel_path: Path, port: int) -> None:
    lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/data":
                panel = json.loads(panel_path.read_text())
                lots = [{k: v for k, v in lot.items() if k != "stratum"} for lot in panel["lots"]]
                self._send(200, json.dumps({"lots": lots, "labels": _read_labels()}).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if self.path != "/label":
                self._send(404, b"not found", "text/plain")
                return
            label = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            if not isinstance(label.get("pin"), str):
                self._send(400, b"pin required", "text/plain")
                return
            with lock:
                labels = _read_labels()
                labels[label["pin"]] = label
                _write_labels(labels)
            self._send(200, json.dumps({"saved": label["pin"], "count": len(labels)}).encode(), "application/json")

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"labeling page on http://localhost:{port}")
    srv.serve_forever()


def score(panel_path: Path) -> dict:
    """Precision of "empty" per stratum and overall (each stratum weighted by its share of the empty pool)."""
    panel = json.loads(panel_path.read_text())
    labels = _read_labels()
    out: dict = {}
    weighted = 0.0
    total_pool = sum(panel["pool"].get(s, 0) for s, _n in STRATA)
    for s, _n in STRATA:
        c = Counter()
        for lot in (x for x in panel["lots"] if x["stratum"] == s):
            c[(labels.get(lot["pin"]) or {}).get("answer") or "unlabeled"] += 1
        decided = sum(v for k, v in c.items() if k not in ("cant_tell", "unlabeled"))
        ok = c["empty"]
        share = ok / decided if decided else None
        out[s] = {**dict(c), "precision": round(share, 3) if share is not None else None, "ci95": _wilson(ok, decided)}
        if share is not None:
            weighted += share * panel["pool"][s] / total_pool
    out["weighted_precision"] = round(weighted, 3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--lots", type=Path, required=True)
    d.add_argument("--sources", type=Path, required=True)
    d.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    d.add_argument("--exclude", type=Path, default=None)
    d.add_argument("--lidar", type=Path, default=None, help="County 2022 LiDAR copy: buildings around the lot")
    d.add_argument("--index", type=Path, default=None, help="Discovery index: the neighbors' own addresses")
    d.add_argument("--out", type=Path, default=PANEL)
    s = sub.add_parser("serve")
    s.add_argument("--panel", type=Path, default=PANEL)
    s.add_argument("--port", type=int, default=8033)
    c = sub.add_parser("score")
    c.add_argument("--panel", type=Path, default=PANEL)
    args = ap.parse_args()
    if args.cmd == "draw":
        print(json.dumps(draw(args.lots, args.sources, args.ptaxsim, args.exclude, args.out, args.lidar, args.index)))
    elif args.cmd == "serve":
        serve(args.panel, args.port)
    else:
        print(json.dumps(score(args.panel), indent=1))


if __name__ == "__main__":
    main()
