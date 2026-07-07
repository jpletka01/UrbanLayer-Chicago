"""Build the precomputed zoning-extraction cache (deterministic full-section fetch).

For every known Chicago zone class, fetches the COMPLETE Title-17 "Bulk and density
standards" section for the zone's district chapter (+ shared parking) and extracts
structured standards via Haiku, writing the result to the committed artifact
`ingestion/data/zoning_cache.json`. The live report path reads that file via
`backend.zoning_cache`. No reranker — `get_full_section()` is a plain Qdrant scroll,
so this runs anywhere with the local Qdrant + ANTHROPIC_API_KEY in a few minutes.

A developer/laptop command (NOT a prod cron). Run after a municipal-code re-ingest
or an extraction-config change, then commit the JSON.

    python -m backend.zoning_cache_build                       # full rebuild
    python -m backend.zoning_cache_build --check               # stale vs current corpus?
    python -m backend.zoning_cache_build --zones RS-3,B3-2     # subset smoke test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

from backend import zoning_cache
from backend.retrieval.zoning_definitions import ZONE_CLASS_DATA

log = logging.getLogger(__name__)


def _enumerate_zone_classes() -> list[str]:
    """The finite set of real Chicago zone classes with extractable standards.

    Sourced directly from the deterministic table (the authoritative list of base
    districts). PD/PMD are intentionally excluded — they have no generic
    extractable standards (site-specific ordinances), so they fall through to the
    table/raw-code path at serve time.
    """
    return sorted(ZONE_CLASS_DATA.keys())


async def _build(zone_classes: list[str]) -> dict:
    entries: dict[str, dict] = {}
    failures: list[str] = []
    from backend.zoning_extract import extract_zoning_standards_from_sections

    for i, zone_class in enumerate(zone_classes, 1):
        log.info("[%d/%d] extracting %s", i, len(zone_classes), zone_class)
        # Bulk section only — feeding the shared parking table alongside it made the
        # extractor grab the wrong FAR row for multi-row business zones (B3-2 → 3.0
        # instead of 2.2). FAR correctness on the paid report outranks parking detail;
        # parking can be a separate-call enhancement later.
        standards, provenance = await extract_zoning_standards_from_sections(
            zone_class, request_group="zoning_cache_build", include_parking=False
        )
        if standards is None:
            failures.append(zone_class)
            continue
        # The deterministic Title-17 table is AUTHORITATIVE for the bulk numbers
        # (FAR / height / lot sizes / per-unit density). AI extraction over the
        # full section gets these mostly right but mis-rows some zones (e.g.
        # B3-1 FAR 3.0 vs true 1.2; B3-1 min-lot 400 vs true 2,500/unit), which
        # is unacceptable on a paid report. The SAME authority pass also runs on
        # every cache read (zoning_cache.get_cached_zoning_standards), so this
        # build-time application only keeps the committed artifact honest when
        # inspected — table corrections never require a rebuild to take effect.
        # AI keeps its value-add: setbacks, parking, special conditions.
        from backend.zoning_extract import apply_table_authority

        apply_table_authority(standards, zone_class)
        entries[zoning_cache._normalize_zone_class(zone_class)] = {
            "standards": standards.model_dump(mode="json"),
            "provenance": provenance,
            "extraction_confidence": standards.extraction_confidence,
        }

    if failures:
        log.warning("Extraction returned nothing for %d zones: %s", len(failures), ", ".join(failures))

    from ingestion.manifest import load_manifest

    meta = {
        "config_version": zoning_cache.compute_config_version(),
        "corpus_fingerprint": zoning_cache.compute_corpus_fingerprint(load_manifest()),
        "built_at": int(time.time()),
        "zone_count": len(entries),
        "extraction_method": "full_section",
    }
    return {"_meta": meta, "entries": entries}


def _write(artifact: dict) -> None:
    path = zoning_cache._cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    log.info(
        "Wrote %d zone entries to %s (config_version=%s corpus_fingerprint=%s)",
        artifact["_meta"]["zone_count"],
        path,
        artifact["_meta"]["config_version"],
        artifact["_meta"]["corpus_fingerprint"],
    )


def _zones_referencing(section_ids: set[str]) -> list[str]:
    """Cached zone classes whose precomputed result drew on any of these sections."""
    path = zoning_cache._cache_path()
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text()).get("entries", {})
    except Exception:
        return []
    targets = set(section_ids)
    return sorted(
        zone for zone, entry in entries.items()
        if targets & set(entry.get("provenance", []))
    )


def staleness_flag(diff, new_manifest: dict, old_manifest: dict) -> str | None:
    """Build a human-readable flag when a code change touches Title-17 (zoning).

    Consumes the manifest diff already computed by `ingestion.update`. Returns
    ``None`` when no Title-17 section changed (zoning cache unaffected).
    """
    changed: set[str] = set()
    for sid in list(diff.added) + list(diff.modified):
        e = new_manifest.get(sid)
        if e is not None and getattr(e, "title_number", None) == 17:
            changed.add(sid)
    for sid in diff.deleted:
        e = old_manifest.get(sid)
        if e is not None and getattr(e, "title_number", None) == 17:
            changed.add(sid)
    if not changed:
        return None

    lines = [
        f"⚠️  {len(changed)} Title-17 (zoning) section(s) changed → precomputed "
        f"zoning cache is likely STALE: {sorted(changed)[:10]}"
    ]
    affected = _zones_referencing(changed)
    if affected:
        lines.append(f"   Affected cached zone classes: {affected[:15]}")
    lines.append("   Rebuild: RERANKER_ENABLED=true python -m backend.zoning_cache_build")
    return "\n".join(lines)


def _check() -> int:
    """Compare the committed cache against the current code corpus. Returns exit code."""
    from ingestion.manifest import load_manifest

    path = zoning_cache._cache_path()
    if not path.exists():
        log.warning("No zoning cache at %s — reports use the table fallback. Build it.", path)
        return 1

    cache = json.loads(path.read_text())
    meta = cache.get("_meta", {})
    cur_config = zoning_cache.compute_config_version()
    cur_corpus = zoning_cache.compute_corpus_fingerprint(load_manifest())

    stale_reasons = []
    if meta.get("config_version") != cur_config:
        stale_reasons.append(
            f"extraction config changed (cache={meta.get('config_version')} code={cur_config})"
        )
    if meta.get("corpus_fingerprint") != cur_corpus:
        stale_reasons.append(
            f"Title-17 corpus changed (cache={meta.get('corpus_fingerprint')} code={cur_corpus})"
        )

    if not stale_reasons:
        log.info("Zoning cache is FRESH (%d zones, config_version=%s).", meta.get("zone_count"), cur_config)
        return 0

    log.warning("Zoning cache is STALE: %s", "; ".join(stale_reasons))
    log.warning("Rebuild: RERANKER_ENABLED=true python -m backend.zoning_cache_build")
    return 2


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report fresh/stale, don't build")
    parser.add_argument("--zones", help="Comma-separated subset of zone classes (smoke test)")
    args = parser.parse_args()

    if args.check:
        raise SystemExit(_check())

    zone_classes = (
        [z.strip().upper() for z in args.zones.split(",") if z.strip()]
        if args.zones
        else _enumerate_zone_classes()
    )
    log.info("Building zoning cache for %d zone classes (full-section fetch)...", len(zone_classes))
    artifact = asyncio.run(_build(zone_classes))
    _write(artifact)


if __name__ == "__main__":
    main()
