"""The one-off prune of rows outside every community-area polygon (backend/discovery/index_prune.py)."""
from __future__ import annotations

import datetime

import pytest

from backend.discovery import index_prune as ip
from backend.discovery.index_build import finalize_index
from backend.discovery.parcel_index import read_index, read_meta, upsert_parcels
from backend.retrieval.utils import format_pin

AS_OF = datetime.date(2025, 1, 1)
_IN, _OUT = (41.9, -87.7), (41.85, -87.75)
# The fixture has 2 of 6 rows outside (33%), above the production guard of 10%, so tests loosen it.
_MAX = 0.5


def _row(digits, point, ca=22):
    lat, lon = point
    return (format_pin(digits), lat, lon, {"total_assessed_value": 100000.0}, [f"neighborhood:{ca}"])


@pytest.fixture
def index(tmp_path, monkeypatch):
    """Four Chicago rows, two suburban rows tagged to a Chicago area (the 2026-10 prod shape)."""
    monkeypatch.setattr(ip.geo, "_polygon_index", lambda: [object()])
    monkeypatch.setattr(ip, "community_area_by_point", lambda lat, lon: 22 if (lat, lon) == _IN else None)
    path = tmp_path / "idx.db"
    upsert_parcels(path, [_row(f"1431100001{i:04d}", _IN) for i in range(4)]
                   + [_row("16311000010000", _OUT, ca=25), _row("16311000020000", _OUT, ca=25)])
    finalize_index(path, community_areas=[22, 25], as_of=AS_OF)
    return path


def test_dry_run_reports_and_writes_nothing(index):
    before = read_meta(index)
    out = ip.prune(index, max_share=_MAX, apply=False)

    assert (out["total"], out["outside"], out["applied"]) == (6, 2, False)
    assert out["tagged_to_ca"] == {"25": 2}
    assert read_meta(index) == before
    assert not index.with_name(index.name + ".pre-prune").exists()


def test_apply_removes_only_outside_rows_backs_up_and_refinalizes(index):
    before = read_meta(index)
    out = ip.prune(index, max_share=_MAX, apply=True, as_of=AS_OF)

    _, parcels = read_index(index)
    assert sorted(p.pin for p in parcels) == [format_pin(f"1431100001{i:04d}") for i in range(4)]
    assert (out["removed"], out["rows_after"], out["applied"]) == (2, 4, True)
    assert out["data_version"] != before.data_version and out["data_version"].endswith("-4p")
    _, backed_up = read_index(index.with_name(index.name + ".pre-prune"))
    assert len(backed_up) == 6  # the earlier state stays recoverable


def test_second_run_is_a_no_op(index):
    ip.prune(index, max_share=_MAX, apply=True, as_of=AS_OF)
    meta = read_meta(index)
    out = ip.prune(index, max_share=_MAX, apply=True, as_of=AS_OF)

    assert (out["outside"], out["applied"]) == (0, False)
    assert read_meta(index) == meta


def test_refuses_when_too_much_looks_outside(index, monkeypatch):
    monkeypatch.setattr(ip, "community_area_by_point", lambda lat, lon: None)  # e.g. a broken polygon file

    with pytest.raises(SystemExit, match="over --max-share"):
        ip.prune(index, max_share=_MAX, apply=True)
    assert len(read_index(index)[1]) == 6


def test_refuses_without_polygons(index, monkeypatch):
    monkeypatch.setattr(ip.geo, "_polygon_index", lambda: [])

    with pytest.raises(SystemExit, match="polygons are not loaded"):
        ip.prune(index, max_share=_MAX, apply=True)


def test_rows_without_coordinates_are_never_deleted(index, monkeypatch):
    upsert_parcels(index, [(format_pin("17000000010000"), None, None, {}, ["neighborhood:22"])])

    out = ip.prune(index, max_share=_MAX, apply=False)

    assert (out["total"], out["outside"]) == (7, 2)
