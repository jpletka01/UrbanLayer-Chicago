"""Item 112 (M5, land in use): the measurement's pure parts and the blind check's blindness."""

import json

import pytest
import shapely

from eval import land_use as lu
from eval import land_use_label as lul


@pytest.mark.parametrize("cls, kind, expected", [
    ("1-00", "vacant", "vacant"),
    ("5-90", "parking", "parking"),
    ("5-80", "parking", "parking"),
    ("2-41", "side_yard", "vacant"),
    ("2-11", "residential", "residential"),
    ("3-15", "residential", "residential"),
    ("5-17", "commercial", "commercial"),
    ("5-93", "commercial", "industrial"),
    ("EX", "exempt", "exempt"),
    ("RR", "railroad", "rail"),
    ("1-00", "city_owned", None),  # who owns it is not what it is used for
    (None, None, None),
])
def test_assessor_crosswalk(cls, kind, expected):
    assert lu.assessor_common(cls, kind) == expected


def test_every_cmap_code_has_a_category():
    # the 57 codes of the 2023 domain table
    assert len(lu.CMAP_COMMON) == 57
    assert lu.CMAP_COMMON["1540"] == "parking"


def test_osm_way_and_multipolygon():
    sq = [{"lon": x, "lat": y} for x, y in ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))]
    g = lu._osm_polygons({"type": "way", "geometry": sq}, {})
    assert g.area == pytest.approx(1.0)
    assert lu._osm_polygons({"type": "way", "geometry": sq[:3]}, {}) is None  # not closed
    hole = [{"lon": x, "lat": y} for x, y in ((.25, .25), (.75, .25), (.75, .75), (.25, .75), (.25, .25))]
    rel = {"type": "relation", "members": [{"type": "way", "role": "outer", "geometry": sq},
                                           {"type": "way", "role": "inner", "geometry": hole}]}
    assert lu._osm_polygons(rel, {}).area == pytest.approx(0.75)


def test_shares_are_of_the_lot():
    lot = shapely.box(0, 0, 2, 1)
    geoms = [shapely.box(0, 0, 1, 1), shapely.box(5, 5, 6, 6)]
    assert lu._shares(lot, lot.area, [0, 1], geoms) == [(0, 0.5)]


def _row(**kw):
    base = {"pin": "x", "lat": 41.9, "lon": -87.7, "structure": "empty", "empty_land": False, "unusual": False,
            "land_kind": "commercial", "assessor": "commercial", "approx_address": True}
    return base | kw


def test_surface_parking_needs_no_building():
    rows = [_row(pin="a", cmap="parking", cmap_share=1.0, cmap_parking_share=1.0),
            _row(pin="b", cmap="parking", cmap_share=1.0, cmap_parking_share=1.0, structure="built"),
            _row(pin="c", osm_surface_parking_share=0.9),
            _row(pin="d", assessor="parking", land_kind="parking", empty_land=True, structure="accessory"),
            _row(pin="e", osm_surface_parking_share=0.2)]
    s = lu.summarize(rows, {})
    assert s["surface_parking_candidates"]["lots"] == 3
    assert s["surface_parking_candidates"]["already_empty_land"] == 1
    assert s["parking_with_building"]["lots"] == 1


@pytest.mark.parametrize("row, stratum", [
    (_row(cmap="parking", cmap_share=1, cmap_parking_share=1, osm_surface_parking_share=1, assessor="parking"),
     "park_all3"),
    (_row(cmap="parking", cmap_share=1, cmap_parking_share=1), "park_cmap_only"),
    (_row(osm_surface_parking_share=0.6), "park_osm_only"),
    (_row(assessor="parking"), "park_assessor_only"),
    (_row(assessor="parking", structure="built"), None),
    (_row(cmap="parking", cmap_share=1, cmap_parking_share=1, structure="built"), "park_garage"),
    (_row(osm_garage_share=0.9, structure="built"), "park_garage"),
    (_row(assessor="vacant", empty_land=True), "empty_no_parking_signal"),
    (_row(assessor="exempt", empty_land=True, cmap="road", cmap_share=0.9), "empty_infra"),
    (_row(assessor="exempt", empty_land=True, cmap="open_space", cmap_share=0.9), "empty_open_space"),
    (_row(assessor="commercial", cmap="commercial", cmap_share=0.9), "nobldg_use_no_parking"),
    (_row(assessor="residential", cmap="residential", cmap_share=0.9, structure="built"), "use_agree"),
    (_row(assessor="residential", cmap="mixed_use", cmap_share=0.9, structure="built"), "use_disagree"),
    (_row(assessor="residential", cmap="residential", cmap_share=0.3, structure="built"), None),
    (_row(assessor="commercial", cmap="road", cmap_share=0.9, structure="built"), None),
    (_row(assessor="parking", unusual=True), None),
])
def test_strata(row, stratum):
    assert lul.stratum_of(row) == stratum


def test_score_counts_by_source(tmp_path, monkeypatch):
    panel = {"pool": {}, "lots": [
        {"pin": "a", "stratum": "park_all3", "truth_keys": {"cmap": "parking", "assessor": "parking", "osm": None,
                                                           "signals": {"cmap": True, "osm": True, "assessor": True}}},
        {"pin": "b", "stratum": "park_assessor_only", "truth_keys": {"cmap": "vacant", "assessor": "parking",
                                                                    "osm": None, "signals": {"cmap": False, "osm": False,
                                                                                             "assessor": True}}},
    ]}
    p = tmp_path / "panel.json"
    p.write_text(json.dumps(panel))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"a": {"answer": "surface_parking"}, "b": {"answer": "empty"}}))
    monkeypatch.setattr(lul, "LABELS", labels)
    out = lul.score(p)
    assert out["surface_by_source"]["assessor"]["precision"] == 0.5
    assert out["surface_by_source"]["cmap"]["precision"] == 1.0
    assert out["surface_rule"]["surface_parking"] == 1 and out["surface_rule"]["decided"] == 2
    assert out["use_precision"]["cmap"] == {}  # parking strata never score a use


def test_score_disagreement_winner(tmp_path, monkeypatch):
    lot = {"pin": "c", "stratum": "use_disagree", "truth_keys": {"cmap": "mixed_use", "assessor": "residential",
                                                                "osm": None, "signals": {}}}
    p = tmp_path / "panel.json"
    p.write_text(json.dumps({"pool": {}, "lots": [lot]}))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"c": {"answer": "commercial"}}))
    monkeypatch.setattr(lul, "LABELS", labels)
    out = lul.score(p)
    assert out["use_disagree_matched"] == {"cmap": 1}
    assert out["use_precision"]["cmap"]["commercial"]["right"] == 1
    assert out["use_precision"]["assessor"]["residential"]["wrong"] == 1


def test_page_is_blind_and_offers_both_views():
    page = lul.PAGE.read_text()
    assert "map_action=pano" in page  # Street View
    assert "!3m1!1e3" in page  # the lot from above, pinned
    for hidden in lul.HIDDEN:
        assert hidden not in page


def test_pair_shares_bulk():
    import numpy as np
    from shapely.strtree import STRtree
    lots = np.array([shapely.box(0, 0, 1, 1), shapely.box(2, 0, 4, 1)], dtype=object)
    geoms = np.array([shapely.box(-1, -1, 2, 2), shapely.box(3, 0, 9, 9)], dtype=object)
    li, gi, sh = lu._pair_shares(lots, STRtree(geoms), geoms)
    got = sorted(zip(li.tolist(), gi.tolist(), [round(x, 3) for x in sh]))
    assert got == [(0, 0, 1.0), (1, 1, 0.5)]
