"""WS8 Phase 0 slice 5: class-weighted projection of which community areas could be colored."""


from eval import capacity_verdicts as cv


def _rec(cls, outcome, source, stratum="unknown_gfa"):
    return {"stratum": stratum, "class": cls, "outcome": outcome, "source": source}


def test_class_group():
    assert [cv.class_group(c) for c in ("2-03", "3-18", "5-17", "EX", None, "1-00")] == ["2", "3", "5", "other", "other", "other"]


def test_group_rates_count_only_the_allowed_sources_and_never_rate_a_fetch_error():
    recs = [
        _rec("5-17", "resolved", "commercial_valuation"),
        _rec("5-17", "resolved", "footprint"),
        _rec("5-17", "unresolved", None),
        _rec("5-17", "fetch_error", None),
        _rec("2-03", "unresolved", None),
        _rec("5-99", "resolved", "commercial_valuation", stratum="condo_bldg"),  # another stratum
    ]
    std = cv.group_rates(recs, cv.STANDARD_SOURCES)
    assert (std["5"]["k"], std["5"]["n"]) == (1, 3)
    assert cv.group_rates(recs, cv.ALL_SOURCES)["5"]["k"] == 2
    assert std["2"]["rate"] == 0.0 and std["3"]["n"] == 0


def test_projection_is_class_weighted_and_carries_the_interval():
    rates = {g: {"rate": 0.0, "lo": 0.0, "hi": 0.0} for g in cv.GROUPS}
    rates["3"] = {"rate": 0.5, "lo": 0.25, "hi": 0.75}
    condo = {"rate": 0.0, "lo": 0.0, "hi": 0.0}
    proj = cv.project_area(now_computable=10, polygons=100, unknown_by_group={"3": 40, "2": 50}, condo_polygons=0, rates=rates, condo=condo)
    assert proj == {"point": 0.3, "low": 0.2, "high": 0.4}


def test_verdict_band_flags_an_interval_that_straddles_a_threshold():
    assert cv.verdict_band({"point": 0.5, "low": 0.4, "high": 0.6}) == {"verdict": "standard", "certain": True, "range": ["standard"]}
    band = cv.verdict_band({"point": 0.12, "low": 0.08, "high": 0.2})
    assert band["verdict"] == "low" and not band["certain"] and band["range"] == ["low", "withheld"]
