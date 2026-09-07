"""Tests for the municipal-code source-hash baseline.

`save_hash()` existed but was never called by any code path until 2026-09-07,
so `source_check` could only ever report "unknown". These lock the round-trip
and the wiring in `ingestion.update`.
"""

from __future__ import annotations

import json

import pytest

from ingestion import source_check


@pytest.fixture
def source_dir(tmp_path, monkeypatch):
    """Point source_check at a scratch data dir with a source HTML file."""
    html = tmp_path / "chicago-il-codes.html"
    html.write_text("<html>original</html>")
    monkeypatch.setattr(source_check, "SOURCE_HTML", html)
    monkeypatch.setattr(source_check, "SOURCE_HASH_FILE", tmp_path / "source_hash.json")
    return tmp_path


def test_check_reports_unknown_before_any_baseline(source_dir):
    result = source_check.check()
    assert result["status"] == "unknown"
    assert result["current_hash"]


def test_check_reports_missing_when_source_absent(source_dir, monkeypatch):
    monkeypatch.setattr(source_check, "SOURCE_HTML", source_dir / "nope.html")
    assert source_check.check()["status"] == "missing"


def test_save_hash_then_check_reports_unchanged(source_dir):
    source_check.save_hash()

    saved = json.loads((source_dir / "source_hash.json").read_text())
    assert saved["hash"]

    assert source_check.check()["status"] == "unchanged"


def test_check_reports_updated_after_source_changes(source_dir):
    source_check.save_hash()
    (source_dir / "chicago-il-codes.html").write_text("<html>fresh download</html>")

    result = source_check.check()
    assert result["status"] == "updated"
    assert result["previous_hash"] != result["current_hash"]


def test_save_hash_no_ops_when_source_absent(source_dir, monkeypatch):
    monkeypatch.setattr(source_check, "SOURCE_HTML", source_dir / "nope.html")
    source_check.save_hash()
    assert not (source_dir / "source_hash.json").exists()


def test_update_manifest_mode_records_the_baseline(tmp_path, monkeypatch):
    """`--manifest` is what source_check's own "unknown" message tells you to run."""
    from ingestion import update

    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "17-1-0100.txt").write_text("body")

    monkeypatch.setattr(update, "SECTIONS_DIR", sections)
    monkeypatch.setattr(update, "CHUNKS_FILE", tmp_path / "chunks.jsonl")
    monkeypatch.setattr(update, "build_manifest", lambda _d: {})
    monkeypatch.setattr(update, "save_manifest", lambda _m: None)

    called: list[bool] = []
    monkeypatch.setattr(update, "save_hash", lambda: called.append(True))
    monkeypatch.setattr("sys.argv", ["update", "--manifest"])

    update.main()

    assert called, "--manifest must record the source-hash baseline"
