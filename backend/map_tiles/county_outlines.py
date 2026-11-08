"""Full-precision parcel outlines for the new UI's map (owner's call, 2026-11-08; decision Item 92).

PTAXSIM stores every outline rounded to 5 decimals (about 1 m), so a straight lot edge draws as small steps.
The County publishes the same outlines at full precision in its GIS parcel layer; the newest year published with
geometry is 2021 (``77tz-riq7``, "ccgisdata - Parcel 2021"). We keep a local copy of Chicago's rows and use a
County outline ONLY where it still describes today's lot: its area within 10% of PTAXSIM's newest outline and the
two overlapping by at least 85% (intersection over union). A lot split, merged or redrawn since 2021 keeps
PTAXSIM's newer outline. Land area, the Profile's figures and the report never read this: it is drawing only.

    PYTHONPATH=. python -m backend.map_tiles.county_outlines [--out backend/data/county_outlines_2021.db]
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from functools import lru_cache
from pathlib import Path

import httpx
import shapely
from shapely.geometry import shape

log = logging.getLogger(__name__)

DATASET = "77tz-riq7"
URL = f"https://datacatalog.cookcountyil.gov/resource/{DATASET}.json"
PAGE = 50_000
MIN_ROWS = 500_000  # Chicago has ~612k; fewer means a partial read
AREA_TOLERANCE = 0.10
MIN_IOU = 0.85


def fetch(out: Path, *, token: str = "") -> dict:
    """Read every Chicago row and write ``out`` (pin10 → WKB, pieces united), beside it then renamed over it."""
    t0 = time.monotonic()
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    pieces: dict[str, list] = {}
    rows = bad = 0
    headers = {"X-App-Token": token} if token else {}
    with httpx.Client(timeout=300, headers=headers) as client:
        offset = 0
        while True:
            r = client.get(URL, params={"$select": "pin10,the_geom", "$where": "municipality='Chicago'",
                                         "$order": ":id", "$limit": PAGE, "$offset": offset})
            r.raise_for_status()
            batch = r.json()
            for row in batch:
                rows += 1
                pin, geom = (row.get("pin10") or "").strip(), row.get("the_geom")
                if len(pin) != 10 or not pin.isdigit() or not geom:
                    bad += 1
                    continue
                g = shape(geom)
                if not g.is_valid:
                    g = shapely.make_valid(g)
                pieces.setdefault(pin, []).append(g)
            log.info("county outlines: %d rows", rows)
            if len(batch) < PAGE:
                break
            offset += PAGE
    if rows < MIN_ROWS:
        raise RuntimeError(f"{DATASET} returned {rows} Chicago rows (expected ~612,000): refusing to write")
    db = sqlite3.connect(tmp)
    db.execute("CREATE TABLE outlines (pin10 TEXT PRIMARY KEY, wkb BLOB NOT NULL)")
    db.execute("CREATE TABLE meta (name TEXT PRIMARY KEY, value TEXT)")
    db.executemany("INSERT INTO outlines VALUES (?, ?)", (
        (pin, shapely.to_wkb(gs[0] if len(gs) == 1 else shapely.union_all(gs))) for pin, gs in pieces.items()))
    summary = {"dataset": DATASET, "rows": rows, "pin10s": len(pieces), "skipped_rows": bad,
               "fetched": time.strftime("%Y-%m-%d"), "seconds": round(time.monotonic() - t0, 1)}
    db.executemany("INSERT INTO meta VALUES (?, ?)", [(k, str(v)) for k, v in summary.items()])
    db.commit()
    db.close()
    tmp.replace(out)
    return summary


class Outlines:
    """Read-only lookups in the local copy (``None`` for every pin10 when the file is missing)."""

    def __init__(self, path: Path):
        self.path = path
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False) if path.exists() else None

    def get(self, pin10: str):
        if self.db is None:
            return None
        row = self.db.execute("SELECT wkb FROM outlines WHERE pin10 = ?", (pin10,)).fetchone()
        return shapely.from_wkb(row[0]) if row else None

    def many(self, pin10s: list[str]) -> dict[str, object]:
        if self.db is None:
            return {}
        out: dict[str, object] = {}
        for i in range(0, len(pin10s), 900):
            chunk = pin10s[i:i + 900]
            q = f"SELECT pin10, wkb FROM outlines WHERE pin10 IN ({','.join('?' * len(chunk))})"
            for pin, wkb in self.db.execute(q, chunk):
                out[pin] = shapely.from_wkb(wkb)
        return out


def still_matches(county, ptaxsim) -> bool:
    """True when the 2021 County outline still describes today's lot (PTAXSIM's newest outline): areas within 10%
    and overlap (intersection over union) of at least 85%. Measured in degrees: both shapes are tiny and at the same
    latitude, so the ratios are unaffected."""
    try:
        a, b = county.area, ptaxsim.area
        if a <= 0 or b <= 0 or abs(a - b) / b > AREA_TOLERANCE:
            return False
        inter = county.intersection(ptaxsim).area
        return inter / (a + b - inter) >= MIN_IOU
    except shapely.errors.GEOSException:
        return False


def best_outline(pin10: str, ptaxsim, outlines: Outlines):
    """The outline to draw: the County's full-precision one when it still matches, else PTAXSIM's. Returns
    (geometry, source) with source "county_2021" or "ptaxsim"."""
    county = outlines.get(pin10)
    if county is not None and ptaxsim is not None and still_matches(county, ptaxsim):
        return county, "county_2021"
    return ptaxsim, "ptaxsim"


@lru_cache(maxsize=1)
def default_outlines() -> Outlines:
    from backend.config import get_settings

    return Outlines(get_settings().county_outlines_path)


def main() -> None:
    from backend.config import get_settings

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=None, help="default: settings.county_outlines_path")
    a = ap.parse_args()
    s = get_settings()
    print(json.dumps(fetch(a.out or s.county_outlines_path, token=s.socrata_app_token), indent=1))


if __name__ == "__main__":
    main()
