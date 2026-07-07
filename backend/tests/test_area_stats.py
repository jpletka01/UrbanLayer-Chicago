"""Area-stats aggregates (Property Profile KPI benchmarks)."""

import json
import sqlite3

import pytest

from backend.retrieval.area_stats import _median, _scan_index, _reset_cache_for_tests


@pytest.fixture(autouse=True)
def _reset():
    _reset_cache_for_tests()


def test_median():
    assert _median([]) is None
    assert _median([5.0]) == 5.0
    assert _median([1.0, 3.0]) == 2.0
    assert _median([1.0, 2.0, 100.0]) == 2.0


def test_scan_index_aggregates(tmp_path):
    db = tmp_path / "idx.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE parcels (pin TEXT PRIMARY KEY, lat REAL, lon REAL, attrs TEXT, regions TEXT)"
    )
    rows = []
    # CA 3: 25 residential parcels (av/psf median must appear per-class at n>=20)
    for i in range(25):
        rows.append((
            f"030000000{i:05d}", 41.9, -87.6,
            json.dumps({"total_assessed_value": 10000 + i * 1000, "land_sqft": 1000,
                        "land_use_class": "residential"}),
            json.dumps(["neighborhood:3"]),
        ))
    # CA 3: a parcel with no AV (counted, not aggregated) + one with junk regions
    rows.append(("03x", 41.9, -87.6, json.dumps({"land_sqft": 500}), json.dumps(["neighborhood:3"])))
    rows.append(("junk", 41.9, -87.6, json.dumps({}), json.dumps(["not-a-region"])))
    # CA 7: 5 parcels — too few for a per-class median, overall still computed
    for i in range(5):
        rows.append((
            f"070000000{i:05d}", 41.9, -87.7,
            json.dumps({"total_assessed_value": 50000, "land_sqft": 2000,
                        "land_use_class": "commercial"}),
            json.dumps(["neighborhood:7"]),
        ))
    conn.executemany("INSERT INTO parcels VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    out = _scan_index(str(db))
    assert set(out) == {3, 7}
    ca3 = out[3]
    assert ca3["n_parcels"] == 26
    assert ca3["median_assessed"] == 22000  # median of 10000..34000
    assert ca3["median_av_per_land_sqft"] == 22.0
    assert "residential" in ca3["by_land_use"]
    ca7 = out[7]
    assert ca7["median_av_per_land_sqft"] == 25.0
    assert ca7["by_land_use"] == {}  # n=5 < floor: a "median" would be an anecdote


@pytest.mark.asyncio
async def test_get_area_stats_missing_index(monkeypatch, tmp_path):
    from backend import config
    from backend.retrieval import area_stats

    class _S:
        discovery_index_path = tmp_path / "absent.db"

    monkeypatch.setattr(area_stats, "get_settings", lambda: _S())
    assert await area_stats.get_area_stats(3) is None
