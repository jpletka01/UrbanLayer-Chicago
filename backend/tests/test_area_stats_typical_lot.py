"""Typical lot size per zoning district in a community area (WS5 PR3, decision Item 66)."""

import json
import sqlite3

from backend.provenance_figures import typical_lot_entry
from backend.retrieval import area_stats


def _index(tmp_path, rows):
    db = tmp_path / "idx.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE parcels (pin TEXT, attrs TEXT, regions TEXT)")
    con.execute("CREATE TABLE meta (id INTEGER, built_at INTEGER)")
    con.execute("INSERT INTO meta VALUES (1, 1793577600)")  # 2026-11-01
    for pin, attrs in rows:
        con.execute("INSERT INTO parcels VALUES (?, ?, ?)", (pin, json.dumps(attrs), json.dumps(["neighborhood:22"])))
    con.commit()
    con.close()
    return str(db)


def _rs3(i: int, land: float, **extra) -> tuple[str, dict]:
    return f"1336{i:06d}0000", {"zone_class": "RS-3", "land_sqft": land, **extra}


def test_the_typical_lot_rests_on_base_parcels_of_that_exact_district(tmp_path):
    rows = [_rs3(i, 3000 + 10 * i) for i in range(60)]                      # 60 lots: 3,000 .. 3,590
    rows += [(f"13360000{i:02d}1001", {"zone_class": "RS-3", "land_sqft": 99999}) for i in range(10)]  # condo unit PINs
    rows += [_rs3(100 + i, 143_900, shared_outline=True) for i in range(5)]   # one outline for a development
    rows += [_rs3(200 + i, 80_000, unusual=True) for i in range(5)]          # a giant no-address vacant lot
    rows += [_rs3(300 + i, None) for i in range(5)]                          # no land area
    rows += [(f"1336{400 + i:06d}0000", {"land_sqft": 3000}) for i in range(5)]  # no district
    rows += [(f"1336{500 + i:06d}0000", {"zone_class": "rt-4 ", "land_sqft": 3125}) for i in range(49)]  # under the floor
    stats = area_stats._scan_index(_index(tmp_path, rows))[22]

    lots = stats["lot_size_by_zone_class"]
    assert set(lots) == {"RS-3"}                     # RT-4 has 49 lots: withheld, not shown thin
    assert lots["RS-3"] == {"n": 60, "p25_lot_sqft": 3148, "median_lot_sqft": 3295, "p75_lot_sqft": 3442}


def test_rt4_appears_once_it_reaches_the_floor(tmp_path):
    rows = [(f"1336{i:06d}0000", {"zone_class": "rt-4 ", "land_sqft": 3125}) for i in range(area_stats.MIN_LOT_N)]
    lots = area_stats._scan_index(_index(tmp_path, rows))[22]["lot_size_by_zone_class"]
    assert lots == {"RT-4": {"n": 50, "p25_lot_sqft": 3125, "median_lot_sqft": 3125, "p75_lot_sqft": 3125}}


def test_an_index_without_zone_class_has_no_typical_lots(tmp_path):
    rows = [(f"1336{i:06d}0000", {"land_sqft": 3000 + i}) for i in range(80)]  # the pre-Item-59 index
    assert area_stats._scan_index(_index(tmp_path, rows))[22]["lot_size_by_zone_class"] == {}


def test_the_entry_names_its_sample_and_the_index_date():
    stats = {"community_area": 22, "index_built": "2026-11-01",
             "lot_size_by_zone_class": {"RS-3": {"n": 4210, "p25_lot_sqft": 3000, "median_lot_sqft": 3125, "p75_lot_sqft": 3750}}}
    entry = typical_lot_entry(stats, "rs-3", qd="2026-11-03")
    assert entry["value"] == 3125 and entry["coverage"]["n"] == 4210 and entry["coverage"]["unit"] == "lots"
    assert entry["as_of"] == "2026-11-01" and entry["confidence"] == "standard" and entry["source_id"] == "internal.discovery_index"
    assert typical_lot_entry(stats, "RT-4", qd="2026-11-03") is None
