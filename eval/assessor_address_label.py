"""A labeled sample for the Assessor-address tier (decision Item 109): is the address Discovery would now show this
lot's own? No model calls; read-only over local copies; the page is served on localhost only.

    PYTHONPATH=. python -m eval.assessor_address_label draw --index <discovery_index.db> --sources <lot_sources.db> \\
        [--ptaxsim backend/data/ptaxsim.db] [--out eval/assessor_address_panel.json]
    PYTHONPATH=. python -m eval.assessor_address_label serve [--panel eval/assessor_address_panel.json] [--port 8032]
    PYTHONPATH=. python -m eval.assessor_address_label score [--panel ...]

**Draw** (seeded): 100 base lots whose Assessor address passes the check. Stratum ``tilde_nearer`` = 50 of the lots
where the old "~" number, on the same street, sits nearer the lot's position than the Assessor's (16,062 citywide: the
riskiest bucket); stratum ``random`` = 50 drawn from every passing lot (80,319), for the overall rate.

**Blind.** Each lot's candidate addresses (the Assessor's and the old "~" one; one when they agree) are shown as A/B in
a seeded order; which is which stays in the panel file, never in what the page receives. The evidence is independent
of both: the lot's outline, its neighbors' outlines with the City's Address Points on them, the street, and Street
View standing on the street facing the lot. The labeler says which candidate is this lot's address, or types the
number seen, or "can't tell".

Labels are saved as they are made to ``eval/results/2026-11-11-assessor-address/labels.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sqlite3
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

PANEL = Path("eval/assessor_address_panel.json")
PAGE = Path(__file__).with_name("assessor_address_label_page.html")
LABELS = Path("eval/results/2026-11-11-assessor-address/labels.json")
SEED = 109
PER_STRATUM = 50
NEAR_FT = 160.0  # neighbors and Address Points drawn around the lot
_FT_LAT = 364_000.0
_FT_LON = _FT_LAT * 0.7447


# ── draw ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _ring(g) -> list[list[float]]:
    g = max(g.geoms, key=lambda x: x.area) if g.geom_type == "MultiPolygon" else g
    return [[round(x, 7), round(y, 7)] for x, y in g.exterior.coords]


def draw(index: Path, sources: Path, ptaxsim: Path, out: Path) -> dict:
    import numpy as np
    import shapely

    from backend.discovery.assessor_address import AddressSources, parse, to_ft, verified_address
    from backend.discovery.index_backfill import lot_outlines

    src = AddressSources.load(sources)
    if src is None:
        raise SystemExit(f"{sources} has no address tables")
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    base = db.execute(
        "SELECT pin, lat, lon, json_extract(attrs, '$.address'), json_extract(attrs, '$.class'), "
        "json_extract(attrs, '$.is_vacant') FROM parcels WHERE pin like '%0000'").fetchall()
    db.close()
    approx = [r for r in base if str(r[3] or "~").startswith("~")]
    assessor, points = src.lookup(r[0].replace("-", "") for r in approx)
    lots = lot_outlines(ptaxsim, {r[0].replace("-", "")[:10] for r in approx})

    passing, nearer = [], []
    for pin, lat, lon, tilde, cls, vacant in approx:
        p14 = pin.replace("-", "")
        lot = lots.get(p14[:10]) or shapely.Point(lon, lat)
        shown, _reason = verified_address(assessor.get(p14), lot, src.streets, points)
        if not shown:
            continue
        rec = {"pin": pin, "lat": lat, "lon": lon, "class": cls, "vacant": bool(vacant), "assessor": shown,
               "assessor_raw": assessor.get(p14), "tilde": (tilde or "")[1:] or None}
        passing.append(rec)
        t = src.streets.resolve(parse(rec["tilde"])) if rec["tilde"] and parse(rec["tilde"]) else None
        a = parse(shown)
        if t and t.street == a.street and t.number != a.number:
            _ok, _r, expected = src.streets.check(a, to_ft(lot))
            if abs(t.number - expected) < abs(a.number - expected):
                nearer.append(rec)

    rnd = random.Random(SEED)
    picked = [dict(r, stratum="tilde_nearer") for r in rnd.sample(nearer, PER_STRATUM)]
    taken = {r["pin"] for r in picked}
    picked += [dict(r, stratum="random") for r in rnd.sample([r for r in passing if r["pin"] not in taken], PER_STRATUM)]
    rnd.shuffle(picked)

    # Evidence: neighbors (index base lots within NEAR_FT, with their own Address Point address) and Address Points.
    lat_a = np.array([r[1] for r in base])
    lon_a = np.array([r[2] for r in base])
    adb = sqlite3.connect(f"file:{sources}?mode=ro", uri=True)
    ap = adb.execute("SELECT address, lon, lat FROM address_points").fetchall()
    adb.close()
    ap_lon = np.array([r[1] for r in ap])
    ap_lat = np.array([r[2] for r in ap])
    near_pins: dict[str, list[int]] = {}
    for r in picked:
        d = np.hypot((lat_a - r["lat"]) * _FT_LAT, (lon_a - r["lon"]) * _FT_LON)
        near_pins[r["pin"]] = [int(i) for i in np.nonzero(d <= NEAR_FT)[0]]
    outlines = lot_outlines(ptaxsim, {base[i][0].replace("-", "")[:10] for v in near_pins.values() for i in v})

    out_lots = []
    for k, r in enumerate(picked):
        p10 = r["pin"].replace("-", "")[:10]
        cands = [("assessor", r["assessor"])]
        if r["tilde"] and r["tilde"] != r["assessor"]:
            cands.append(("tilde", r["tilde"]))
        rnd.shuffle(cands)
        neighbors = []
        for i in near_pins[r["pin"]]:
            pin, _la, _lo, addr = base[i][:4]
            o = outlines.get(pin.replace("-", "")[:10])
            if o is None or pin == r["pin"]:
                continue
            neighbors.append({"ring": _ring(o), "address": addr if addr and not str(addr).startswith("~") else None})
        d = np.hypot((ap_lat - r["lat"]) * _FT_LAT, (ap_lon - r["lon"]) * _FT_LON)
        aps = [{"address": ap[i][0], "lon": ap[i][1], "lat": ap[i][2]} for i in np.nonzero(d <= NEAR_FT)[0]]
        a = parse(r["assessor"])
        street = _street_lines(src.streets, a, r["lat"], r["lon"])
        own = lots.get(p10)
        out_lots.append({
            "id": k + 1, "pin": r["pin"], "stratum": r["stratum"], "lat": r["lat"], "lon": r["lon"],
            "class": r["class"], "vacant": r["vacant"],
            "candidates": [{"key": "AB"[j], "address": c[1], "source": c[0]} for j, c in enumerate(cands)],
            "assessor_raw": r["assessor_raw"],
            "ring": _ring(own) if own is not None else None, "neighbors": neighbors, "address_points": aps,
            "street": street, "viewpoint": _viewpoint(street, r["lat"], r["lon"]),
        })
    body = {"seed": SEED, "drawn_from": {"passing": len(passing), "tilde_nearer": len(nearer)}, "lots": out_lots}
    out.write_text(json.dumps(body, indent=1))
    return body["drawn_from"]


def _street_lines(streets, parsed, lat: float, lon: float) -> list[list[list[float]]]:
    """The address street's centerline pieces near the lot, lon/lat."""
    import shapely

    from backend.discovery.assessor_address import to_ft

    out = []
    c = to_ft(shapely.Point(lon, lat))
    for f in streets._faces.get(parsed.street, []):
        if f.line.distance(c) <= 300:
            out.append([[round(x / _FT_LON, 7), round(y / _FT_LAT, 7)] for x, y in f.line.coords])
    return out


def _viewpoint(street: list, lat: float, lon: float) -> dict | None:
    """The point on the street nearest the lot, and the heading from it to the lot (degrees from north)."""
    from shapely.geometry import LineString, Point

    best = None
    for line in street:
        ls = LineString([(x * _FT_LON, y * _FT_LAT) for x, y in line])
        c = Point(lon * _FT_LON, lat * _FT_LAT)
        p = ls.interpolate(ls.project(c))
        d = p.distance(c)
        if best is None or d < best[0]:
            best = (d, p, c)
    if best is None:
        return None
    _d, p, c = best
    heading = (math.degrees(math.atan2(c.x - p.x, c.y - p.y)) + 360) % 360
    return {"lat": round(p.y / _FT_LAT, 7), "lon": round(p.x / _FT_LON, 7), "heading": round(heading)}


# ── serve ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _read_labels() -> dict:
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}


def _write_labels(labels: dict) -> None:
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=LABELS.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(labels, f, indent=1, sort_keys=True)
    os.replace(tmp, LABELS)


def _blind(panel: dict) -> dict:
    """What the page receives: no candidate's source, no stratum, no raw Assessor string."""
    lots = []
    for lot in panel["lots"]:
        b = {k: v for k, v in lot.items() if k not in ("stratum", "assessor_raw")}
        b["candidates"] = [{"key": c["key"], "address": c["address"]} for c in lot["candidates"]]
        lots.append(b)
    return {"lots": lots}


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
                body = {"panel": _blind(json.loads(panel_path.read_text())), "labels": _read_labels()}
                self._send(200, json.dumps(body).encode(), "application/json")
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


# ── score ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def score(panel_path: Path) -> dict:
    """Per stratum: how often the Assessor's address is this lot's, the old "~" one is, neither is, and can't tell."""
    panel = json.loads(panel_path.read_text())
    labels = _read_labels()
    out: dict = {"drawn_from": panel["drawn_from"]}
    for stratum in ("tilde_nearer", "random"):
        tally = {"assessor_right": 0, "tilde_right": 0, "neither": 0, "cant_tell": 0, "unlabeled": 0}
        wrong = []
        for lot in (x for x in panel["lots"] if x["stratum"] == stratum):
            lab = labels.get(lot["pin"])
            if not lab or not lab.get("answer"):
                tally["unlabeled"] += 1
                continue
            src = {c["key"]: c["source"] for c in lot["candidates"]}
            ans = lab["answer"]
            if ans == "cant_tell":
                tally["cant_tell"] += 1
            elif ans == "neither":
                tally["neither"] += 1
            elif src.get(ans) == "assessor":
                tally["assessor_right"] += 1
            else:
                tally["tilde_right"] += 1
            if ans != "cant_tell" and src.get(ans) != "assessor":
                wrong.append({"id": lot["id"], "pin": lot["pin"],
                              "shown": next(c["address"] for c in lot["candidates"] if c["source"] == "assessor"),
                              "seen": lab.get("number") or next((c["address"] for c in lot["candidates"]
                                                                  if c["key"] == ans), None)})
        decided = tally["assessor_right"] + tally["tilde_right"] + tally["neither"]
        out[stratum] = {**tally, "assessor_right_share": round(tally["assessor_right"] / decided, 3) if decided else None,
                        "ci95": _wilson(tally["assessor_right"], decided), "wrong": wrong}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--index", type=Path, required=True)
    d.add_argument("--sources", type=Path, required=True)
    d.add_argument("--ptaxsim", type=Path, default=Path("backend/data/ptaxsim.db"))
    d.add_argument("--out", type=Path, default=PANEL)
    s = sub.add_parser("serve")
    s.add_argument("--panel", type=Path, default=PANEL)
    s.add_argument("--port", type=int, default=8032)
    c = sub.add_parser("score")
    c.add_argument("--panel", type=Path, default=PANEL)
    args = ap.parse_args()
    if args.cmd == "draw":
        print(json.dumps(draw(args.index, args.sources, args.ptaxsim, args.out)))
    elif args.cmd == "serve":
        serve(args.panel, args.port)
    else:
        print(json.dumps(score(args.panel), indent=1))


if __name__ == "__main__":
    main()
