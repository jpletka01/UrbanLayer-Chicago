"""The committed Commercial Valuation artifact: its builder's summary, the loader's three answers, and the committed
file itself (WS8 Phase 1, decision Item 39)."""

import gzip
import json

import pytest

from backend.retrieval.property import commercial_artifact as ca
from ingestion import build_commercial_bldg_artifact as builder


def _write(tmp_path, units, year="2024"):
    path = tmp_path / "commercial_bldg_by_pin.json.gz"
    artifact = {"assessor": {"dataset": "csik-bsws", "year": year}, "columns": ["keypin", "bldg_sqft", "pins"], "units": units}
    builder.write(artifact, {"built_at": "2026-10-31"}, out=path, meta_out=tmp_path / "commercial_bldg_by_pin.meta.json")
    ca._load.cache_clear()
    return path


def test_summarize_sums_rows_and_keeps_members():
    rows = [
        # A split-class building: one row per class portion, each with its own area.
        {"keypin": "09-25-407-023-0000", "pins": "09-25-407-023-0000, 09-25-407-024-0000", "bldgsf": "6694.0"},
        {"keypin": "09-25-407-023-0000", "pins": "09-25-407-023-0000, 09-25-407-024-0000", "bldgsf": "11906.0"},
        {"keypin": "09-25-407-023-0000", "pins": "09-25-407-023-0000, 09-25-407-024-0000"},
        {"keypin": "20-03-422-020-0000", "pins": "20-03-422-020-0000"},  # no area on any row
        {"keypin": "17-09-100-001-0000", "bldgsf": "1200"},  # no pins list: the keypin alone
    ]
    assert builder.summarize(rows) == [
        ["09254070230000", 18600, ["09254070230000", "09254070240000"]],
        ["17091000010000", 1200, ["17091000010000"]],
        ["20034220200000", None, ["20034220200000"]],
    ]


def test_write_is_deterministic(tmp_path):
    units = [["17091000010000", 1200, ["17091000010000"]]]
    a = _write(tmp_path, units).read_bytes()
    b = _write(tmp_path, units).read_bytes()
    assert a == b


def test_single_pin_unit_is_attributed(tmp_path):
    path = _write(tmp_path, [["17091000010000", 1200, ["17091000010000"]]])
    got = ca.building_area("17-09-100-001-0000", path)
    assert got == ca.UnitArea(1200.0, ("17091000010000",), "2024")


def test_unit_on_one_base_parcel_is_attributed(tmp_path):
    """Members that share a PIN10 are one polygon: the area belongs to that lot."""
    path = _write(tmp_path, [["17091000010000", 5000, ["17091000010000", "17091000011001"]]])
    assert isinstance(ca.building_area("17091000010000", path), ca.UnitArea)


def test_complex_total_never_lands_on_one_lot_keypin_included(tmp_path):
    path = _write(tmp_path, [["09254070230000", 18600, ["09254070230000", "09254070240000"]]])
    for pin in ("09254070230000", "09254070240000"):
        got = ca.building_area(pin, path)
        assert isinstance(got, ca.MultiPinMember), pin
        assert got.complex_bldg_sqft == 18600.0


def test_pin_in_two_units_has_no_single_answer(tmp_path):
    path = _write(tmp_path, [["11111111110000", 100, ["11111111110000"]], ["22222222220000", 900, ["22222222220000", "11111111110000"]]])
    got = ca.building_area("11111111110000", path)
    assert isinstance(got, ca.MultiPinMember) and got.complex_bldg_sqft is None


def test_not_in_any_unit_or_no_area_is_none(tmp_path):
    path = _write(tmp_path, [["20034220200000", None, ["20034220200000"]]])
    assert ca.building_area("20034220200000", path) is None
    assert ca.building_area("99999999990000", path) is None


def test_missing_or_broken_artifact_raises(tmp_path):
    ca._load.cache_clear()
    with pytest.raises(ca.CapacityArtifactError):
        ca.building_area("17091000010000", tmp_path / "absent.json.gz")
    bad = tmp_path / "bad.json.gz"
    bad.write_bytes(gzip.compress(b"{not json"))
    with pytest.raises(ca.CapacityArtifactError):
        ca.artifact_year(bad)


def test_committed_artifact_matches_its_sidecar():
    if not ca.ARTIFACT_PATH.exists():
        pytest.skip("artifact not present")
    ca._load.cache_clear()
    with gzip.open(ca.ARTIFACT_PATH, "rt") as fh:
        data = json.load(fh)
    meta = json.loads(ca.ARTIFACT_PATH.with_name("commercial_bldg_by_pin.meta.json").read_text())
    assert data["assessor"]["year"] == meta["assessor_year"] == ca.artifact_year()
    assert len(data["units"]) == meta["units"]
    assert sum(1 for _, a, _ in data["units"] if a is not None) == meta["units_with_area"]
    assert all(len(p) == 14 and p.isdigit() for _, _, pins in data["units"][:500] for p in pins)


def test_ci_age_check_and_sidecar_name(tmp_path):
    from datetime import date

    from backend.data_health import artifacts
    from backend.data_health.registry import BY_ID, sidecar_locator

    spec = BY_ID[ca.SOURCE_ID]
    assert spec.locator == "ingestion/data/commercial_bldg_by_pin.json.gz"
    assert sidecar_locator(spec.locator) == "ingestion/data/commercial_bldg_by_pin.meta.json"
    side = tmp_path / "ingestion/data/commercial_bldg_by_pin.meta.json"
    side.parent.mkdir(parents=True)
    side.write_text(json.dumps({"built_at": "2026-10-31", "assessor_year": "2024"}))
    assert artifacts.check_commercial_bldg(date(2026, 11, 1), tmp_path).state == "ok"
    assert "2027 reassessment is due" in artifacts.check_commercial_bldg(date(2027, 3, 1), tmp_path).message
    assert artifacts.check_commercial_bldg(date(2031, 1, 1), tmp_path).state == "alarm"
    side.unlink()
    assert artifacts.check_commercial_bldg(date(2026, 11, 1), tmp_path).state == "warn"
