"""The Assessor-address tier for Discovery lots with no Address Point (decision Item 109)."""

from __future__ import annotations

import sqlite3

import pytest
import shapely
from shapely.geometry import LineString, box

from backend.discovery import assessor_address as aa
from backend.discovery.index_backfill import apply_assessor_addresses
from backend.discovery.lot_sources import _write_addresses

FT_LAT = 1 / 364_000.0
FT_LON = FT_LAT / 0.7447
LON0, LAT0 = -87.70, 41.8440  # the 2600 block's north end


def _segment(name="TROY", typ="ST"):
    """A 1,000 ft block of S <name> digitized north to south: 2600-2698 even on the right (west), odd on the left."""
    line = LineString([(LON0, LAT0), (LON0, LAT0 - 1000 * FT_LAT)])
    return ("S", name, typ, 2601, 2699, 2600, 2698, "O", "E", shapely.to_wkb(line))


def _lot(ft_south: float, ft_west: float = 40.0):
    """A 25 x 100 ft lot whose centroid is ``ft_south`` down the block and ``ft_west`` of the centerline."""
    cx, cy = LON0 - ft_west * FT_LON, LAT0 - ft_south * FT_LAT
    return box(cx - 50 * FT_LON, cy - 12.5 * FT_LAT, cx + 50 * FT_LON, cy + 12.5 * FT_LAT)


@pytest.fixture
def streets():
    return aa.Streets([_segment(), ("N", "ST LOUIS", "AVE", 0, 0, 0, 0, None, None,
                                    shapely.to_wkb(LineString([(-87.71, 41.9), (-87.71, 41.901)]))),
                       ("N", "BROADWAY", None, 0, 0, 0, 0, None, None,
                        shapely.to_wkb(LineString([(-87.65, 41.95), (-87.65, 41.951)])))])


def test_parse_drops_unit_tails_and_refuses_placeholders():
    assert aa.parse("2626 S TROY ST").base == "2626 S TROY ST"
    p = aa.parse("1217 W LEXINGTON ST B")
    assert (p.base, p.unit) == ("1217 W LEXINGTON ST", "B")
    assert aa.parse("10420 S WALDEN PKY REAR").base == "10420 S WALDEN PKWY"
    assert aa.parse("10913 S AVENUE E").base == "10913 S AVENUE E"
    for placeholder in ("W TILDEN AVE", "1538 RAILROAD", "UNKNOWN", "0 W 26TH ST", "", None):
        assert aa.parse(placeholder) is None


def test_the_city_spelling_is_used(streets):
    assert streets.resolve(aa.parse("4410 N SAINT LOUIS AVE")).base == "4410 N ST LOUIS AVE"
    assert streets.resolve(aa.parse("5000 N BROADWAY ST")).base == "5000 N BROADWAY"
    assert streets.resolve(aa.parse("5000 N NOWHERE ST")) is None


def test_the_address_must_land_on_the_lot(streets):
    lot = _lot(270)  # 27% down the block: the position implies about 2626
    assert aa.verified_address("2626 S TROY ST", lot, streets, None) == ("2626 S TROY ST", "ok")
    assert aa.verified_address("2626 S TROY ST 2 FL", lot, streets, None) == ("2626 S TROY ST", "ok")
    assert aa.verified_address("2627 S TROY ST", lot, streets, None)[1] == "off_block_face"  # odd: across the street
    assert aa.verified_address("2660 S TROY ST", lot, streets, None)[1] == "off_position"  # same side, a block-third on
    assert aa.verified_address("2726 S TROY ST", lot, streets, None)[1] == "off_block_face"  # the next block
    assert aa.verified_address("2626 S TROY ST", _lot(270, ft_west=400), streets, None)[1] == "street_far"
    assert aa.verified_address("2626 S KEDZIE AVE", lot, streets, None)[1] == "no_street"
    assert aa.verified_address("W TILDEN AVE", lot, streets, None) == (None, "placeholder")
    assert aa.verified_address(None, lot, streets, None) == (None, "no_address")


def test_an_address_point_elsewhere_means_another_building(streets):
    lot = _lot(270)
    far = (LON0 - 40 * FT_LON, LAT0 - 600 * FT_LAT)  # 330 ft down the block
    on = lot.centroid.coords[0]
    assert aa.verified_address("2626 S TROY ST", lot, streets, {"2626 S TROY ST": [far]})[1] == "address_point_elsewhere"
    assert aa.verified_address("2626 S TROY ST", lot, streets, {"2626 S TROY ST": [far, on]})[1] == "ok"


def test_apply_replaces_only_an_approximate_address_and_reruns_restore_it():
    attrs = {"address": "~2624 S TROY ST", "own_address": False}
    aa.apply(attrs, "2626 S TROY ST")
    assert attrs == {"address": "2626 S TROY ST", "address_source": "assessor", "address_nearest": "~2624 S TROY ST",
                     "own_address": False}  # own_address stays the Address Points' answer (Item 60's hidden set)
    assert aa.needs_tier(attrs)
    aa.apply(attrs, None)  # a rerun whose check now fails
    assert attrs == {"address": "~2624 S TROY ST", "own_address": False}
    own = {"address": "2626 S TROY ST", "own_address": True}
    aa.apply(own, "2628 S TROY ST")
    assert own == {"address": "2626 S TROY ST", "own_address": True}
    assert not aa.needs_tier(own)
    none = {}
    aa.apply(none, "2626 S TROY ST")
    assert none == {"address": "2626 S TROY ST", "address_source": "assessor"}
    aa.apply(none, None)
    assert none == {}


def _sources(tmp_path, assessor):
    path = tmp_path / "lot_sources.db"
    db = sqlite3.connect(path)
    with db:
        _write_addresses(db, "2026", assessor, [("2624 S TROY ST", LON0 - 40 * FT_LON, LAT0 - 240 * FT_LAT)],
                         [_segment()])
    db.close()
    return path


def test_the_builder_pass_uses_the_local_copy(tmp_path):
    path = _sources(tmp_path, [("16253000300000", "2626 S TROY ST"), ("16253000310000", "2690 S TROY ST")])
    lot = _lot(270)
    rows = [
        ("16-25-300-030-0000", lot.centroid.y, lot.centroid.x, {"address": "~2624 S TROY ST", "own_address": False}, []),
        # no outline: the parcel point stands in; the Assessor's number is a block-half away
        ("16-25-300-031-0000", lot.centroid.y, lot.centroid.x, {"address": "~2624 S TROY ST", "own_address": False}, []),
        ("16-25-300-032-0000", lot.centroid.y, lot.centroid.x, {"address": "2628 S TROY ST", "own_address": True}, []),
        ("16-25-300-030-1001", lot.centroid.y, lot.centroid.x, {"address": "~2624 S TROY ST"}, []),  # a unit PIN
    ]
    out = apply_assessor_addresses(rows, {"1625300030": lot}, path)
    assert rows[0][3]["address"] == "2626 S TROY ST" and rows[0][3]["address_source"] == "assessor"
    assert rows[1][3]["address"] == "~2624 S TROY ST"
    assert rows[2][3] == {"address": "2628 S TROY ST", "own_address": True}
    assert rows[3][3] == {"address": "~2624 S TROY ST"}
    assert out == {"ok": 1, "off_position": 1}


def test_a_copy_without_the_address_tables_changes_nothing(tmp_path):
    path = tmp_path / "old.db"
    sqlite3.connect(path).execute("CREATE TABLE footprints (x)").connection.close()
    rows = [("16-25-300-030-0000", LAT0, LON0, {"address": "~2624 S TROY ST"}, [])]
    assert apply_assessor_addresses(rows, {}, path) == {}
    assert rows[0][3] == {"address": "~2624 S TROY ST"}
