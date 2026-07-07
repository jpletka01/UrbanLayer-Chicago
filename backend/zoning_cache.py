"""Precomputed zoning-extraction cache (report path).

The report's zoning extraction (`extract_zoning_standards`) fires 5 reranked
vector searches per parcel. On the prod vCPUs a reranked search is ~40s, so the
report path can't run the reranker live without 504ing. But the 5 queries are
fully templated on `zone_class` (`ZONING_QUERY_TEMPLATES`), so the result is a
pure function of (zone_class, code content, retrieval+extraction config) — i.e.
precomputable.

This module is the READ side: it loads a small committed JSON artifact
(`ingestion/data/zoning_cache.json`, built off-box by `backend.zoning_cache_build`
with the reranker on) and serves `ZoningStandards` by zone class. A miss or a
config-version mismatch returns ``None`` so the caller falls back to the existing
deterministic Title-17 table — the cache is a pure quality uplift that can never
hang the report.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.models import ZoningStandards

log = logging.getLogger(__name__)

CACHE_FILENAME = "zoning_cache.json"

# Loaded artifact, or {} when absent/invalid/stale. ``None`` means "not yet loaded".
# Tests reset this to None to force a reload (mirrors the transit_stations pattern).
_cache: dict[str, Any] | None = None


def _cache_path() -> Path:
    return get_settings().data_dir / CACHE_FILENAME


def _normalize_zone_class(zone_class: str) -> str:
    """Cache key for a zone class.

    Collapses numbered planned developments (``PD-1234`` → ``PD``): the PD number
    isn't in the code text, so reranked retrieval returns generic PD sections
    regardless. (No ``PD`` entry is built — the table/raw-code path handles PDs —
    so this just keeps the unbounded PD space from polluting the key space.)
    """
    s = (zone_class or "").strip().upper()
    if s.startswith("PD-") or s == "PD":
        return "PD"
    return s


def compute_config_version() -> str:
    """Fingerprint of every input that determines a cached entry's *content*.

    If any of these change in code, a stale cache must be ignored (and rebuilt):
    the bulk-section map + parking section the builder feeds, and the extraction
    prompt + model. (The builder uses deterministic full-section retrieval, so the
    reranker no longer affects cache content.)
    """
    from backend.zoning_extract import (
        BULK_SECTION_BY_PREFIX,
        EXTRACTION_SYSTEM,
        SHARED_PARKING_SECTION,
    )

    s = get_settings()
    payload = json.dumps(
        {
            "bulk_section_map": BULK_SECTION_BY_PREFIX,
            "shared_parking_section": SHARED_PARKING_SECTION,
            "extraction_system": EXTRACTION_SYSTEM,
            "zoning_extract_model": s.zoning_extract_model,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def compute_corpus_fingerprint(manifest: dict[str, Any]) -> str:
    """Fingerprint of the Title-17 corpus the cache was built against.

    Hash over sorted ``(section_id, content_hash)`` for Title-17 sections only
    (zoning lives in Title 17). Drift means the zoning code changed → cache stale.
    Build/flag-time only — the serving read path does not need the manifest.
    Accepts any mapping of ``section_id -> entry`` where ``entry`` has
    ``content_hash`` and ``title_number`` (ingestion.manifest.SectionEntry).
    """
    items = sorted(
        (sid, e.content_hash)
        for sid, e in manifest.items()
        if getattr(e, "title_number", None) == 17
    )
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache

    path = _cache_path()
    if not path.exists():
        log.info(
            "Zoning cache not found at %s — reports use the Title-17 table fallback. "
            "Build with `python -m backend.zoning_cache_build`.",
            path,
        )
        _cache = {}
        return _cache

    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        log.warning("Failed to load zoning cache %s: %s", path, exc)
        _cache = {}
        return _cache

    cache_version = data.get("_meta", {}).get("config_version")
    expected = compute_config_version()
    if cache_version != expected:
        log.warning(
            "Zoning cache config_version mismatch (cache=%s, code=%s) — ignoring cache, "
            "using Title-17 table fallback. Rebuild with `python -m backend.zoning_cache_build`.",
            cache_version,
            expected,
        )
        _cache = {}
        return _cache

    _cache = data
    return _cache


def get_cached_zoning_standards(zone_class: str | None) -> ZoningStandards | None:
    """Return precomputed `ZoningStandards` for a zone class, or ``None`` on miss/stale.

    A ``None`` return is the caller's signal to use the existing R1 Title-17 table
    fallback — never to run the live reranker on the report path.

    The deterministic table authority is re-applied on every read (not only at
    build time): ``config_version`` fingerprints the extraction inputs, so a
    correction to ``zoning_definitions.py`` alone would otherwise leave the
    committed artifact serving the old bulk numbers until someone remembered to
    rebuild (2026-07-06 audit — exactly how fabricated heights shipped at
    "high" confidence).
    """
    if not zone_class:
        return None
    entry = _load().get("entries", {}).get(_normalize_zone_class(zone_class))
    if not entry:
        return None
    try:
        standards = ZoningStandards.model_validate(entry["standards"])
    except Exception as exc:
        log.warning("Invalid cached zoning entry for %s: %s", zone_class, exc)
        return None
    from backend.zoning_extract import apply_table_authority

    return apply_table_authority(standards, zone_class)


def reset_cache() -> None:
    """Drop the in-memory cache so the next access reloads from disk (tests)."""
    global _cache
    _cache = None
