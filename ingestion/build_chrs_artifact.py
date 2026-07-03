"""One-time converter: CHRS orange/red KML → committed runtime artifact.

The Chicago Historic Resources Survey (1996) is frozen — the Socrata API
asset (``ty7a-2bxt``) is 403-restricted, but the raw file downloads work:

    curl -L -o chrs.zip \
      "https://data.cityofchicago.org/download/cmb2-8jw8/application%2Foctet-stream"
    unzip chrs.zip     # -> doc.kml (~23 MB)
    python -m ingestion.build_chrs_artifact doc.kml

Output: ``ingestion/data/chrs_orange_red.json.gz`` — one record per surviving
orange/red-rated building footprint::

    {"color": "orange"|"red", "name": ..., "address": ...,
     "lat": ..., "lon": ..., "ring": [[lon, lat], ...]}

COLOR_ID mapping verified against known CHRS-red landmarks (Holy Trinity
Orthodox Cathedral, Old Colony Building, Elks National Memorial — all
COLOR_ID=2): **1 = orange, 2 = red**. Rows with DELETED=Y or other COLOR_IDs
(13 of 9,291) are dropped. Consumed by ``backend/retrieval/property/chrs.py``
(shapely point-in-polygon at request time).
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

OUT_PATH = Path(__file__).parent / "data" / "chrs_orange_red.json.gz"

_COLORS = {"1": "orange", "2": "red"}


def _field(pm: str, name: str) -> str:
    m = re.search(rf"{name}</td>\s*<td>(.*?)</td>", pm, re.S)
    if not m:
        return ""
    val = m.group(1).strip()
    return "" if val == "&lt;Null&gt;" else val


def _address(pm: str) -> str:
    low, high = _field(pm, "LOW_ADDR"), _field(pm, "HIGH_ADDR")
    number = low if (not high or high == low) else f"{low}-{high}"
    parts = [number, _field(pm, "DIRECTION"), _field(pm, "STREET_NAME"),
             _field(pm, "STREET_TYPE")]
    return " ".join(p for p in parts if p and p != ".")


def build(kml_path: str) -> None:
    text = Path(kml_path).read_text(encoding="utf-8")
    placemarks = re.findall(r"<Placemark.*?</Placemark>", text, re.S)
    records = []
    for pm in placemarks:
        color = _COLORS.get(_field(pm, "COLOR_ID"))
        if color is None or _field(pm, "DELETED") == "Y":
            continue
        m = re.search(r"<coordinates>\s*(.*?)\s*</coordinates>", pm, re.S)
        if not m:
            continue
        ring = []
        for pair in m.group(1).split():
            lon, lat = pair.split(",")[:2]
            ring.append([round(float(lon), 6), round(float(lat), 6)])
        if len(ring) < 4:
            continue
        lats = [p[1] for p in ring]
        lons = [p[0] for p in ring]
        name = _field(pm, "LANDMARKNAME")
        records.append({
            "color": color,
            "name": name if name and name.lower() != "null" else None,
            "address": _address(pm) or None,
            "lat": round(sum(lats) / len(lats), 6),
            "lon": round(sum(lons) / len(lons), 6),
            "ring": ring,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_PATH, "wt", encoding="utf-8") as fh:
        json.dump(records, fh, separators=(",", ":"))
    counts = {c: sum(1 for r in records if r["color"] == c) for c in ("orange", "red")}
    print(f"{len(records)} footprints ({counts}) -> {OUT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m ingestion.build_chrs_artifact <doc.kml>")
    build(sys.argv[1])
