"""Tests for the CHRS orange/red local-artifact lookup (backend/retrieval/property/chrs.py)."""

import gzip
import json

import pytest

from backend.config import get_settings
from backend.retrieval.property import chrs


@pytest.fixture(autouse=True)
def _fresh_tree():
    chrs.reset_for_tests()
    yield
    chrs.reset_for_tests()


def _artifact():
    path = get_settings().data_dir / chrs.ARTIFACT_FILENAME
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def test_artifact_ships_orange_and_red():
    records = _artifact()
    colors = {r["color"] for r in records}
    assert colors == {"orange", "red"}
    assert len(records) > 9000  # 1996 survey: ~9.1k orange + ~150 red


def test_lookup_hits_a_known_red_building():
    """The first red record's own centroid must resolve to that rating."""
    red = next(r for r in _artifact() if r["color"] == "red")
    hit = chrs.lookup_chrs(red["lat"], red["lon"])
    assert hit is not None
    assert hit["color"] == "red"


def test_lookup_hits_a_known_orange_building():
    orange = next(r for r in _artifact() if r["color"] == "orange")
    hit = chrs.lookup_chrs(orange["lat"], orange["lon"])
    assert hit is not None
    assert hit["color"] == "orange"


def test_lookup_misses_open_water():
    assert chrs.lookup_chrs(41.9000, -87.5500) is None  # Lake Michigan


def test_missing_artifact_degrades_silently(monkeypatch, tmp_path):
    monkeypatch.setattr(chrs, "ARTIFACT_FILENAME", "does_not_exist.json.gz")
    assert chrs.lookup_chrs(41.88, -87.63) is None
