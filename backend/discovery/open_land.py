"""Parks and water on each lot (decision Item 128, the owner's map review of 2026-11-16).

The base map draws Chicago Park District parks (``ejsh-fztr``) and the City's water (``knfe-65pw``) from local copies
in ``map_sources/`` (``backend.map_tiles.base_tiles``); this measures how much of every lot outline each covers, once,
so ``lot_facts.mark_land_use`` can say a lot is a park or water and give it no room to build.

The audit that found them (``eval/map_audit.py``, the local citywide copy): 3,609 lots at least half inside a park (CMAP
2023 calls 92% open space; 99% tax-exempt), 3,419 of them drawn "not known"; 573 lots at least half under water (the
North Branch's riverbed parcels, the Calumet basins), 410 drawn "not known".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

PARKS_FILE, WATER_FILE = "ejsh-fztr.json", "knfe-65pw.json"


def present(folder: Path) -> bool:
    return all((folder / f).exists() and (folder / f).stat().st_size for f in (PARKS_FILE, WATER_FILE))


def polygons(path: Path) -> np.ndarray:
    from backend.map_tiles.base_tiles import is_island

    out = []
    for r in json.loads(path.read_text()):
        if r.get("the_geom") and not is_island(r):
            g = shape(r["the_geom"])
            out.append(g if g.is_valid else shapely.make_valid(g))
    if not out:
        raise RuntimeError(f"{path} has no polygons")
    return np.array(out, dtype=object)


def shares(lots: np.ndarray, polys: np.ndarray) -> dict[int, float]:
    """Lot index -> the share of the lot the polygons cover (overlaps between polygons capped at 1)."""
    from backend.discovery.cmap_land_use import pair_shares

    acc: dict[int, float] = {}
    for li, _gi, sh in zip(*pair_shares(lots, STRtree(polys), polys)):
        acc[int(li)] = acc.get(int(li), 0.0) + float(sh)
    return {k: min(v, 1.0) for k, v in acc.items()}


def open_land_on_lots(folder: Path, pins: list[str], lots: list) -> list[tuple[str, float, float]]:
    """(pin10, park share, water share) for every lot a park or water touches."""
    arr = np.array(lots, dtype=object)
    park = shares(arr, polygons(folder / PARKS_FILE))
    water = shares(arr, polygons(folder / WATER_FILE))
    return [(pins[i], round(park.get(i, 0.0), 3), round(water.get(i, 0.0), 3)) for i in sorted(set(park) | set(water))]
