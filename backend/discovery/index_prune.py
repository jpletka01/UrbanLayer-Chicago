"""One-off repair: remove rows outside every community-area polygon from an existing Discovery index.

The 2026-10-29 production refresh kept the ~66.7k suburban rows because the builder's prune matched
the wrong PIN form (see `decisions/2026-10_discovery-index.md`, Item 2). Rebuilding the whole index
to drop them takes ~4.5 h; this deletes exactly those rows from the file in place and re-runs the
finalize pass (cross-parcel fields, `populated_fields`, `recipe_counts`, a new `data_version`).

    python -m backend.discovery.index_prune            # dry run: counts only, writes nothing
    python -m backend.discovery.index_prune --apply    # back up the file, delete, finalize, verify

A row is "outside" when `community_area_by_point` (the builder's and the census's test) finds no
polygon for its point. Rows with no coordinates are never deleted. Restart the backend afterwards:
it reads the index once at startup.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import sqlite3
from collections import Counter
from pathlib import Path

from backend.discovery.index_build import finalize_index
from backend.discovery.parcel_index import (
    default_index_path,
    delete_parcels,
    iter_parcel_rows,
    read_meta,
)
from backend.retrieval import geo
from backend.retrieval.geo import community_area_by_point

log = logging.getLogger(__name__)

# The audit found 7.03% outside. A far larger share means the polygons or the coordinates are wrong,
# not that the index is full of suburbs, so refuse rather than delete a city.
DEFAULT_MAX_SHARE = 0.10


def find_outside(path: Path) -> tuple[list[str], int, Counter]:
    """Stream the index and return (outside PINs as stored, total rows, outside count per stored CA tag)."""
    outside: list[str] = []
    tagged: Counter = Counter()
    total = 0
    for pin, lat, lon, _attrs, regions in iter_parcel_rows(path):
        total += 1
        if lat is None or lon is None or community_area_by_point(lat, lon) is not None:
            continue
        outside.append(pin)
        tagged[next((r.split(":", 1)[1] for r in regions if r.startswith("neighborhood:")), "none")] += 1
    return outside, total, tagged


def backup(path: Path) -> Path:
    """Consistent copy next to the index (SQLite online backup, safe while the file is in WAL mode)."""
    dest = path.with_name(path.name + ".pre-prune")
    if dest.exists():
        raise SystemExit(f"{dest} already exists; move it aside first (it is the only copy of the earlier state)")
    src = sqlite3.connect(path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def prune(path: Path, *, apply: bool, max_share: float = DEFAULT_MAX_SHARE,
          as_of: datetime.date | None = None) -> dict:
    """Plan (and with `apply`, carry out) the prune. Returns what was found and done."""
    meta = read_meta(path) if path.exists() else None
    if meta is None:
        raise SystemExit(f"no finalized index at {path}")
    if not geo._polygon_index():
        raise SystemExit("community-area polygons are not loaded; every row would look outside")

    outside, total, tagged = find_outside(path)
    share = len(outside) / total if total else 0.0
    result = {"total": total, "outside": len(outside), "share": round(share, 4),
              "tagged_to_ca": dict(tagged.most_common(8)), "applied": False}
    if share > max_share:
        raise SystemExit(f"{len(outside)} of {total} rows ({share:.1%}) are outside; over --max-share "
                         f"{max_share:.0%}, so nothing was changed")
    if not apply or not outside:
        return result

    result["backup"] = str(backup(path))
    removed = delete_parcels(path, outside)
    if removed != len(outside):
        raise SystemExit(f"deleted {removed} rows, expected {len(outside)}; the backup is at {result['backup']}")
    data_version, count = finalize_index(
        path, community_areas=meta.community_areas, as_of=as_of or datetime.date.today(),
    )
    remaining, after_total, _ = find_outside(path)
    if remaining or after_total != total - removed:
        raise SystemExit(f"verification failed: {len(remaining)} outside, {after_total} rows "
                         f"(expected 0 and {total - removed}); the backup is at {result['backup']}")
    result.update(applied=True, removed=removed, data_version=data_version, rows_after=count)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Remove rows outside every community-area polygon from the index.")
    ap.add_argument("--apply", action="store_true", help="delete (default is a dry run that writes nothing)")
    ap.add_argument("--max-share", type=float, default=DEFAULT_MAX_SHARE,
                    help="refuse when more than this share of rows is outside (default 0.10)")
    return ap.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()
    out = prune(default_index_path(), apply=args.apply, max_share=args.max_share)
    for k, v in out.items():
        print(f"{k}: {v}")
    if not args.apply:
        print("dry run: nothing was written. Re-run with --apply to delete.")
