from eval import capacity_map_panel as mp


def _row(view, polygons, colorable, verdict="standard", unchecked=(), reason=None, states=None):
    body = {"summary": {"polygons": polygons, "colorable": colorable, "colorable_share": colorable / polygons if polygons else 0.0,
                        "verdict": verdict, "states": states or {"computable": colorable}},
            "unchecked": list(unchecked), "reason": reason}
    return mp.view_row(view, body, 0.1)


def test_pooled_counts_only_drawn_views():
    rows = [_row("a", 10, 8), _row("b", 30, 3, "low"), _row("c", 0, 0, "withheld", reason="parcel_not_in_index"),
            _row("d", 5, 5, unchecked=["zoning"])]
    s = mp.pooled(rows)
    assert s["views"] == 4 and s["drawn"] == 2
    assert s["not_drawn"] == {"parcel_not_in_index": 1, "zoning": 1}
    assert s["colorable_share_pooled"] == round(11 / 40, 4)
    assert s["verdicts"] == {"standard": 1, "low": 1}


def test_view_row_keeps_only_nonzero_states():
    r = _row("a", 4, 1, states={"computable": 1, "exempt": 3, "vacant_land": 0})
    assert r["states"] == {"computable": 1, "exempt": 3}
