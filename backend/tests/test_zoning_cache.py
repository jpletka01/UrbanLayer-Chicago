"""Tests for the precomputed zoning cache read path + staleness tooling."""

from __future__ import annotations

import json

import pytest

from backend import zoning_cache
from backend.models import ZoningStandards


@pytest.fixture(autouse=True)
def _reset_cache():
    zoning_cache.reset_cache()
    yield
    zoning_cache.reset_cache()


def _write_cache(tmp_path, monkeypatch, entries, *, config_version=None):
    """Write a cache artifact and point the module at it."""
    cv = config_version if config_version is not None else zoning_cache.compute_config_version()
    path = tmp_path / "zoning_cache.json"
    path.write_text(json.dumps({
        "_meta": {"config_version": cv, "corpus_fingerprint": "x", "built_at": 0,
                  "zone_count": len(entries), "reranker_model": "m"},
        "entries": entries,
    }))
    monkeypatch.setattr(zoning_cache, "_cache_path", lambda: path)
    zoning_cache.reset_cache()
    return path


def _entry(**kw):
    s = ZoningStandards(extraction_confidence="high", **kw)
    return {"standards": s.model_dump(mode="json"), "provenance": ["17-2-0303"],
            "extraction_confidence": "high"}


def test_cache_hit_returns_standards(tmp_path, monkeypatch):
    """A cache hit serves the entry — with the Title-17 table authority applied
    on READ: a stored mis-row (far=2.5) or stale height can never reach a
    report, whatever the artifact says (2026-07-06 audit). AI-only fields
    (setbacks) pass through untouched."""
    _write_cache(tmp_path, monkeypatch, {
        "RM-5": _entry(far=2.5, max_height_ft=99, lot_coverage_pct=0.6, rear_setback_ft=30),
    })
    out = zoning_cache.get_cached_zoning_standards("RM-5")
    assert out is not None
    assert out.far == 2.0            # table-authoritative (Table 17-2-0304)
    assert out.max_height_ft == 45   # lowest ordinance tier (Table 17-2-0305)
    assert out.lot_coverage_pct is None  # not a Title-17 standard
    assert out.min_lot_area_sqft == 1650
    assert out.min_lot_area_per_unit_sqft == 400
    assert out.rear_setback_ft == 30  # AI value-add survives


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    _write_cache(tmp_path, monkeypatch, {"RM-5": _entry(far=2.5)})
    assert zoning_cache.get_cached_zoning_standards("B3-2") is None


def test_blank_zone_class_returns_none(tmp_path, monkeypatch):
    _write_cache(tmp_path, monkeypatch, {"RM-5": _entry(far=2.5)})
    assert zoning_cache.get_cached_zoning_standards(None) is None
    assert zoning_cache.get_cached_zoning_standards("") is None


def test_zone_class_normalized_for_lookup(tmp_path, monkeypatch):
    _write_cache(tmp_path, monkeypatch, {"RS-3": _entry(far=0.9)})
    # lowercase / whitespace normalizes to the stored key
    assert zoning_cache.get_cached_zoning_standards(" rs-3 ") is not None


def test_pd_normalization_collapses_to_miss(tmp_path, monkeypatch):
    # numbered PDs collapse to "PD"; no PD entry is built → miss → table fallback
    assert zoning_cache._normalize_zone_class("PD-1234") == "PD"
    assert zoning_cache._normalize_zone_class("pd-987") == "PD"
    _write_cache(tmp_path, monkeypatch, {"RM-5": _entry(far=2.5)})
    assert zoning_cache.get_cached_zoning_standards("PD-1234") is None


def test_config_version_mismatch_ignores_whole_cache(tmp_path, monkeypatch):
    _write_cache(tmp_path, monkeypatch, {"RM-5": _entry(far=2.5)}, config_version="STALE000")
    assert zoning_cache.get_cached_zoning_standards("RM-5") is None


def test_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(zoning_cache, "_cache_path", lambda: tmp_path / "nope.json")
    zoning_cache.reset_cache()
    assert zoning_cache.get_cached_zoning_standards("RM-5") is None


def test_malformed_entry_returns_none(tmp_path, monkeypatch):
    _write_cache(tmp_path, monkeypatch, {"RM-5": {"standards": {"far": "not-a-number"}}})
    assert zoning_cache.get_cached_zoning_standards("RM-5") is None


# --- versioning / fingerprint helpers ---

class _Entry:
    def __init__(self, content_hash, title_number):
        self.content_hash = content_hash
        self.title_number = title_number


def test_corpus_fingerprint_only_tracks_title_17():
    base = {"17-2-0303": _Entry("aaa", 17), "10-1-0100": _Entry("bbb", 10)}
    fp = zoning_cache.compute_corpus_fingerprint(base)
    # a non-Title-17 change does NOT move the fingerprint
    changed_other = {"17-2-0303": _Entry("aaa", 17), "10-1-0100": _Entry("ZZZ", 10)}
    assert zoning_cache.compute_corpus_fingerprint(changed_other) == fp
    # a Title-17 change DOES
    changed_t17 = {"17-2-0303": _Entry("ZZZ", 17), "10-1-0100": _Entry("bbb", 10)}
    assert zoning_cache.compute_corpus_fingerprint(changed_t17) != fp


def test_config_version_is_deterministic_and_sensitive(monkeypatch):
    v1 = zoning_cache.compute_config_version()
    assert v1 == zoning_cache.compute_config_version()
    import backend.zoning_extract as ze
    monkeypatch.setattr(ze, "BULK_SECTION_BY_PREFIX", {**ze.BULK_SECTION_BY_PREFIX, "ZZ": "17-9-9999"})
    assert zoning_cache.compute_config_version() != v1


def test_bulk_section_mapping():
    from backend.zoning_extract import _bulk_section_for
    assert _bulk_section_for("RM-5") == "17-2-0300"   # residential
    assert _bulk_section_for("RS-3") == "17-2-0300"
    assert _bulk_section_for("B3-2") == "17-3-0400"    # business
    assert _bulk_section_for("C1-2") == "17-3-0400"    # commercial
    assert _bulk_section_for("DX-7") == "17-4-0400"    # downtown
    assert _bulk_section_for("M1-2") == "17-5-0400"    # manufacturing
    assert _bulk_section_for("rm-5") == "17-2-0300"    # case-insensitive
    assert _bulk_section_for("POS-1") is None          # no chapter bulk table → table fallback
    assert _bulk_section_for("PD-1234") is None
    assert _bulk_section_for("") is None


def test_staleness_flag_fires_on_title17_change(tmp_path, monkeypatch):
    from backend.zoning_cache_build import staleness_flag
    from ingestion.manifest import ManifestDiff

    _write_cache(tmp_path, monkeypatch, {"RM-5": _entry(far=2.5)})  # provenance ["17-2-0303"]
    new_manifest = {"17-2-0303": _Entry("new", 17)}
    diff = ManifestDiff(added=[], modified=["17-2-0303"], deleted=[])
    flag = staleness_flag(diff, new_manifest, {})
    assert flag is not None and "RM-5" in flag

    # a non-Title-17 change produces no flag
    diff2 = ManifestDiff(added=[], modified=["10-1-0100"], deleted=[])
    assert staleness_flag(diff2, {"10-1-0100": _Entry("x", 10)}, {}) is None
