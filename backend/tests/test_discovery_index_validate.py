"""PR-VAL: pure pieces of the non-blocking index validation harness."""

from __future__ import annotations

from backend.discovery.index_validate import (
    _distribution,
    _extract_parcel_keys,
    _percentile_rank,
    cross_check,
)


def test_distribution():
    d = _distribution([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert d["n"] == 10 and d["min"] == 1 and d["max"] == 10
    assert d["p50"] in (5, 6)  # mid
    assert _distribution([])["n"] == 0


def test_percentile_rank():
    pop = sorted([10, 20, 30, 40])
    assert _percentile_rank(pop, 10) == 0.0      # cheapest/lowest
    assert _percentile_rank(pop, 30) == 50.0
    assert _percentile_rank([], 5) == 0.0


def test_extract_parcel_keys_to_10_digit_prefix():
    # 14-digit (dashed) and 10-digit permit PINs both reduce to the shared 10-digit parcel key,
    # NOT shattered on dashes nor left-padded (the bug that caused 0 overlap with the index).
    assert _extract_parcel_keys("13-36-301-006-0000") == ["1336301006"]
    assert _extract_parcel_keys("1708320016") == ["1708320016"]  # 10-digit permit PIN
    assert _extract_parcel_keys("13363010060000, 13363010070000") == ["1336301006", "1336301007"]
    assert _extract_parcel_keys(None) == []
    assert _extract_parcel_keys("123") == []  # too short


def test_cross_check_elevated_vs_weak():
    # upside high for the redeveloped pins -> elevated signal
    upside = {f"p{i}": float(i) for i in range(100)}  # 0..99
    hi = [f"p{i}" for i in range(90, 100)]  # top decile
    res = cross_check(upside, hi)
    assert res["matched"] == 10 and res["signal"] == "elevated"
    assert res["median_upside_percentile"] >= 55
    # average pins -> weak/none
    mid = [f"p{i}" for i in range(45, 55)]
    assert cross_check(upside, mid)["signal"] == "weak/none"
    # no overlap -> n=0
    assert cross_check(upside, ["zzz"])["matched"] == 0
