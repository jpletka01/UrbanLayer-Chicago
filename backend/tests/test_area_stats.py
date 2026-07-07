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
    # CA 3: 25 residential parcels (mv/psf median must appear per-class at n>=20)
    for i in range(25):
        rows.append((
            f"030000000{i:05d}", 41.9, -87.6,
            json.dumps({"total_assessed_value": 10000 + i * 1000, "land_sqft": 1000,
                        "class": "2-05", "land_use_class": "residential"}),
            json.dumps(["neighborhood:3"]),
        ))
    # CA 3: a parcel with no AV (counted, not aggregated) + one with junk regions
    rows.append(("03x", 41.9, -87.6, json.dumps({"land_sqft": 500}), json.dumps(["neighborhood:3"])))
    rows.append(("junk", 41.9, -87.6, json.dumps({}), json.dumps(["not-a-region"])))
    # CA 3: an exempt parcel with a (bogus) AV — no assessment level, so it
    # counts toward the AV median but NEVER toward the $/ft² benchmark.
    rows.append((
        "03ex", 41.9, -87.6,
        json.dumps({"total_assessed_value": 22000, "land_sqft": 100,
                    "class": "EX", "land_use_class": "exempt"}),
        json.dumps(["neighborhood:3"]),
    ))
    # CA 7: 5 commercial parcels — too few for a per-class median, overall
    # still computed AND level-normalized (25% class-5 level, not 10%).
    for i in range(5):
        rows.append((
            f"070000000{i:05d}", 41.9, -87.7,
            json.dumps({"total_assessed_value": 50000, "land_sqft": 2000,
                        "class": "5-17", "land_use_class": "commercial"}),
            json.dumps(["neighborhood:7"]),
        ))
    conn.executemany("INSERT INTO parcels VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    out = _scan_index(str(db))
    assert set(out) == {3, 7}
    ca3 = out[3]
    assert ca3["n_parcels"] == 27
    assert ca3["median_assessed"] == 22000  # median of 10000..34000 + one 22000
    assert ca3["n_assessed"] == 26
    # Market value per land ft²: AV 22,000 ÷ 0.10 level ÷ 1,000 ft² = $220/ft².
    # Raw AV/ft² would have said 22 — the class-level normalization IS the fix.
    assert ca3["median_mv_per_land_sqft"] == 220.0
    assert ca3["n_mv_psf"] == 25  # exempt parcel excluded (no level)
    assert ca3["by_land_use"]["residential"]["median_mv_per_land_sqft"] == 220.0
    ca7 = out[7]
    # Commercial: AV 50,000 ÷ 0.25 ÷ 2,000 = $100/ft² (10% would say 250).
    assert ca7["median_mv_per_land_sqft"] == 100.0
    assert ca7["n_mv_psf"] == 5
    assert ca7["by_land_use"] == {}  # n=5 < floor: a "median" would be an anecdote


@pytest.mark.asyncio
async def test_get_area_stats_missing_index(monkeypatch, tmp_path):
    from backend import config
    from backend.retrieval import area_stats

    class _S:
        discovery_index_path = tmp_path / "absent.db"

    monkeypatch.setattr(area_stats, "get_settings", lambda: _S())
    assert await area_stats.get_area_stats(3) is None
