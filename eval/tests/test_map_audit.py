"""Item 128 (the owner's map review): the citywide map audit's findings."""

from eval import map_audit as ma


def _r(**kw):
    base = {"pin": "x", "address": "~1 N STATE ST", "class": "EX", "land_kind": "exempt", "structure": "empty",
            "zone": None, "zoning_group": None, "infrastructure": None, "unusual": False, "room_sqft": None,
            "room_scope": None, "bldg_sqft_unknown": "no_footprint", "land_sqft": 1000.0, "r": None, "l": None,
            "cmap": None, "cmap_share": 0.0}
    return base | kw


def test_findings_sort_unknown_and_room_lots_by_what_covers_them():
    recs = [
        _r(park_share=0.99),  # unknown park
        _r(cmap="1360", cmap_share=0.99),  # unknown cemetery
        _r(water_share=0.8),  # unknown water and over water
        _r(r="4", park_share=0.9),  # room on a park
        _r(r="p", park_share=0.9),  # a park already named: no finding
        _r(r="4", cmap="1360", cmap_share=0.9, **{"cta_ft": 40.0}),  # room on a cemetery, and a line through
        _r(r="t", infrastructure="rail", **{"cta_ft": 400.0}),  # rail land: not "unmarked"
    ]
    s = ma.summarize(recs)
    assert s["unknown_park"]["lots"] == 1 and s["unknown_cemetery"]["lots"] == 1 and s["unknown_water"]["lots"] == 1
    assert s["room_on_park"]["lots"] == 1 and s["room_on_cemetery"]["lots"] == 1
    assert s["lots_over_water"]["lots"] == 1
    assert s["line_through_unmarked"]["lots"] == 1 and s["line_through_unmarked"]["by_r"] == {"4": 1}
    assert s["unknown"]["lots"] == 3
