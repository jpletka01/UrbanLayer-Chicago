"""Production parcel-snapshot loading + the current dataVersion pointer.

This is the seam between the pure evaluator and the parcel data. `evaluate` reads the
immutable snapshot bound to a `data_version` (INV-2); this module decides which snapshot
is "current" and how it is built.

The real source is the precomputed PIN-keyed *prospecting index* built offline by
`index_build.py` (strategy Part B). `ensure_loaded()` reads it from `discovery_index.db`
when present; until an index is built it registers an empty snapshot so the endpoint is
live and correct but returns no parcels.
"""

from __future__ import annotations

import logging
import re

from backend.discovery.parcel import Parcel, default_source
from backend.discovery.parcel_index import IndexMeta, default_index_path, read_index, read_meta

log = logging.getLogger(__name__)

# Used only when no prospecting index has been built yet (INV-2 is per version).
EMPTY_VERSION = "discovery-empty-0"

_current_version: str | None = None
# The loaded index's meta (coverage + populatedFields source). None = no index / dormant.
_current_meta: IndexMeta | None = None

# Memoized pin→parcel map for the current snapshot. The snapshot is immutable per dataVersion,
# so this is built once and reused across requests rather than rebuilt O(N) on every hydrate —
# which matters at the ~1.8M-parcel (`--all`) scale. Invalidated whenever the snapshot changes.
_pin_index: dict[str, Parcel] | None = None
_pin_index_version: str | None = None
_pin10_index: dict[str, Parcel] | None = None
_pin10_index_version: str | None = None


def set_snapshot(version: str, parcels: list[Parcel], *, meta: IndexMeta | None = None) -> None:
    """Register a snapshot and make it the current one (used by the loader + tests).

    `meta` carries coverage + populatedFields; omitting it (the default) leaves the
    registry reporting coverage "none" + empty populatedFields — the safe dormant state.
    """
    global _current_version, _current_meta, _pin_index, _pin_index_version, _pin10_index, _pin10_index_version
    default_source.register(version, parcels)
    _current_version = version
    _current_meta = meta
    _pin_index = None  # invalidate the memoized pin→parcel map (snapshot changed)
    _pin_index_version = None
    _pin10_index = None
    _pin10_index_version = None


def pin_lookup(version: str) -> dict[str, Parcel]:
    """Cached pin→parcel map for `version`, rebuilt only when the dataVersion changes."""
    global _pin_index, _pin_index_version
    if _pin_index is None or _pin_index_version != version:
        _pin_index = {p.pin: p for p in default_source.get(version)}
        _pin_index_version = version
    return _pin_index


def pin10_lookup(version: str) -> dict[str, Parcel]:
    """Cached PIN10 → parcel map for `version`: what a map outline (one per PIN10, decision Item 68) opens.

    A PIN10 holds a base parcel (suffix 0000) and, for a condo building, its unit PINs. The base parcel
    wins; otherwise the lowest PIN. Keys are digits only, whatever the index's PIN spelling."""
    global _pin10_index, _pin10_index_version
    if _pin10_index is None or _pin10_index_version != version:
        out: dict[str, Parcel] = {}
        for p in default_source.get(version):
            digits = re.sub(r"\D", "", p.pin)
            if len(digits) < 10:
                continue
            key = digits[:10]
            have = out.get(key)
            if have is None:
                out[key] = p
                continue
            have_digits = re.sub(r"\D", "", have.pin)
            if have_digits.endswith("0000") and len(have_digits) == 14:
                continue
            if (digits.endswith("0000") and len(digits) == 14) or digits < have_digits:
                out[key] = p
        _pin10_index = out
        _pin10_index_version = version
    return _pin10_index


def current_version() -> str:
    if _current_version is None:
        raise RuntimeError("discovery: no parcel snapshot loaded; call ensure_loaded() first")
    return _current_version


def current_meta() -> IndexMeta | None:
    """The loaded index's meta, or None when no index is built (→ dormant defaults)."""
    return _current_meta


def ensure_loaded() -> None:
    """Idempotent startup hook — guarantees a current snapshot exists.

    Loads the prospecting index from `discovery_index.db` if one has been built; otherwise
    falls back to an empty snapshot so the endpoint stays correct (just returns nothing).
    """
    if _current_version is not None:
        return
    path = default_index_path()
    data_version, parcels = read_index(path)
    if data_version is not None:
        set_snapshot(data_version, parcels, meta=read_meta(path))
        log.info("discovery: loaded %s parcels from index %s", len(parcels), data_version)
        return
    set_snapshot(EMPTY_VERSION, [], meta=None)
    log.warning(
        "discovery: no prospecting index built — /discovery/search will return empty. "
        "Build one with `python -m backend.discovery.index_build --community-areas <ids>`."
    )
