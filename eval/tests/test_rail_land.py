"""Item 121 (rail land): the measurement's pure parts and the blind check's blindness."""

import json

import numpy as np
import pytest
import shapely
from shapely.strtree import STRtree

from eval import rail_land as rl
from eval import rail_land_label as rll


def _lot(**kw):
    base = {"pin": "14-18-500-008-0000", "lat": 41.96, "lon": -87.69, "class": "EX", "land_kind": "exempt",
            "structure": "empty", "empty_land": True, "unusual": False}
    return base | kw


@pytest.mark.parametrize("extra, expected", [
    ({}, "none"),
    ({"cmap_rail_share": 0.92}, "cmap"),
    ({"cmap_rail_share": 0.49}, "none"),  # under half the lot
    ({"cmap_rail_share": 0.9, "cta_elevated_ft": 60.0}, "cmap+cta"),
    ({"cta_elevated_ft": 24.0}, "none"),  # a line clipping a corner
    ({"narn_main_ft": 20.0, "narn_yard_ft": 10.0}, "narn"),
    ({"narn_industry_ft": 300.0}, "none"),  # an industry spur runs into a factory: never rail land on its own
    ({"cta_subway_ft": 300.0}, "none"),  # a lot over the subway is buildable
    ({"class": "RR"}, "rr_class"),
])
def test_combo(extra, expected):
    assert rl.combo(_lot(**extra)) == expected


@pytest.mark.parametrize("extra, expected", [
    ({"cmap_rail_share": 0.9, "cta_elevated_ft": 60.0}, "cmap_cta"),
    ({"cmap_rail_share": 0.9, "narn_main_ft": 60.0}, "cmap_narn"),
    ({"cmap_rail_share": 0.9, "narn_main_ft": 60.0, "cta_elevated_ft": 60.0}, "cmap_narn"),
    ({"cmap_rail_share": 0.9}, "cmap_only"),
    ({"cmap_rail_share": 0.9, "empty_land": False, "structure": "disagree"}, "cmap_not_empty"),
    ({"cta_elevated_ft": 60.0}, "cta_only_empty"),
    ({"cta_elevated_ft": 60.0, "empty_land": False, "structure": "built"}, "cta_only_other"),
    ({"narn_yard_ft": 60.0}, "narn_only_empty"),
    ({"cta_elevated_ft": 60.0, "infrastructure": "road", "unusual": True}, "road_with_cta"),
    ({"infrastructure": "road", "unusual": True}, None),
    ({"near_line": True}, "near_line_no_source"),
    ({"cmap_rail_share": 0.9, "unusual": True}, None),  # hidden today for another reason
    ({"class": "RR", "cmap_rail_share": 0.9}, None),  # railroad class: hidden since Item 60
    ({"no_outline": True, "cmap_rail_share": 0.9}, None),
])
def test_stratum(extra, expected):
    assert rll.stratum_of(_lot(**extra)) == expected


def test_feet_projection_is_close_to_true_distance():
    # one block (1/8 mile = 660 ft) north and one east of the projection's origin
    north = rl.to_feet(shapely.LineString([(-87.65, 41.85), (-87.65, 41.85 + 660 / 364_000)]))
    assert north.length == pytest.approx(660, rel=0.001)
    east = rl.to_feet(shapely.LineString([(-87.65, 41.85), (-87.65 + 660 / rl._FT_PER_DEG_LON, 41.85)]))
    assert east.length == pytest.approx(660, rel=0.001)


def test_line_agreement_counts_points_inside_and_near():
    box = shapely.box(0, 0, 1000, 100)
    on = shapely.LineString([(0, 50), (1000, 50)])  # inside the whole way
    off = shapely.LineString([(0, 140), (1000, 140)])  # 40 ft north of it
    geoms = np.array([box], dtype=object)
    a = rl.line_agreement([on], STRtree(geoms), geoms)
    assert a["inside"] == 1.0 and a["p90_ft"] == 0
    b = rl.line_agreement([off], STRtree(geoms), geoms)
    assert b["inside"] == 0.0 and b["within_25ft"] == 0.0 and b["within_50ft"] == 1.0


def test_load_lines_sorts_kinds_and_drops_abandoned(tmp_path):
    (tmp_path / "cta_lines.json").write_text(json.dumps([
        {"the_geom": {"type": "LineString", "coordinates": [[-87.69, 41.96], [-87.68, 41.96]]},
         "type": "Elevated or At Grade", "lines": "Brown Line", "legend": "BR"},
        {"the_geom": {"type": "LineString", "coordinates": [[-87.63, 41.88], [-87.63, 41.89]]},
         "type": "Subway", "lines": "Red Line", "legend": "RD"},
    ]))
    line = {"type": "LineString", "coordinates": [[-87.7, 41.8], [-87.7, 41.81]]}
    (tmp_path / "narn_lines.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": line, "properties": {"NET": n, "RROWNER1": "UP"}}
        for n in ("M", "Y", "I", "A", "T", "X", "R")]}))
    got = rl.load_lines(tmp_path)
    assert {k: len(v) for k, v in got.items()} == {"cta_elevated": 1, "cta_subway": 1, "narn_main": 1,
                                                    "narn_yard": 1, "narn_industry": 1}


def test_the_panel_page_never_sees_the_sources_or_the_stratum():
    panel = json.loads(rll.PANEL.read_text())
    assert len(panel["lots"]) == sum(n for _s, n in rll.STRATA)
    for lot in panel["lots"]:
        blind = {k: v for k, v in lot.items() if k not in rll.lul.HIDDEN}
        text = json.dumps(blind)
        for word in ("stratum", "truth_keys", "cmap", "cta_elevated", "narn"):
            assert word not in text
