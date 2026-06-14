"""Production parcel-snapshot loading + the current dataVersion pointer.

This is the seam between the pure evaluator and the parcel data. `evaluate` reads the
immutable snapshot bound to a `data_version` (INV-2); this module decides which snapshot
is "current" and how it is built.

⚠️ The real source — a precomputed PIN-keyed *prospecting index* joining 25+ filterable
attributes + offline spatial flags across ~1.8M parcels — is a deliberately separate
Phase-2 engineering build (see `claude-context/strategy/property-discovery-filters.md`
Part B: "not a prerequisite" for the filter/evaluator design). Until that index ships,
`ensure_loaded()` registers an empty snapshot so the endpoint is live and correct but
returns no parcels. No frontend consumes it yet (FE is steps 8–9).
"""

from __future__ import annotations

import logging

from backend.discovery.parcel import Parcel, default_source

log = logging.getLogger(__name__)

# Bumped whenever the underlying parcel snapshot content changes (INV-2 is per version).
EMPTY_VERSION = "discovery-empty-0"

_current_version: str | None = None


def set_snapshot(version: str, parcels: list[Parcel]) -> None:
    """Register a snapshot and make it the current one (used by the loader + tests)."""
    global _current_version
    default_source.register(version, parcels)
    _current_version = version


def current_version() -> str:
    if _current_version is None:
        raise RuntimeError("discovery: no parcel snapshot loaded; call ensure_loaded() first")
    return _current_version


def ensure_loaded() -> None:
    """Idempotent startup hook — guarantees a current snapshot exists.

    Replace the empty registration with the prospecting-index loader when Part B ships.
    """
    if _current_version is not None:
        return
    set_snapshot(EMPTY_VERSION, [])
    log.warning(
        "discovery: no prospecting index wired — /discovery/search will return empty. "
        "See strategy/property-discovery-filters.md Part B."
    )
