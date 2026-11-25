"""Nominal assessments ($1 common areas, remnants of divided lots) are statements, not values (decision Item 46).

The reference parcel is PIN 14-28-319-102-0000: class 100, $1 certified/Board total every year 2022-2026,
beside ten class-100 lots carrying $2,142,695 each and ~456 condo units.
"""

import json
import sqlite3

import pytest

from backend.discovery.parcel_index import derive_sort_fields
from backend.models import PropertySummary
from backend.report_builder import _resolve_market_value_and_tax
from backend.retrieval.area_stats import _scan_index
from backend.retrieval.property import _build_summary
from backend.retrieval.property.assessment_level import is_nominal_assessment


@pytest.mark.parametrize(
    ("total", "cls", "prior", "expected"),
    [
        (1.0, "1-00", None, True),
        (99.0, "2-03", None, True),
        (0.0, "1-00", None, True),
        (100.0, "1-00", None, False),
        (250_000.0, "2-11", None, False),
        (None, "1-00", None, False),
        (1.0, "EX", None, False),  # exempt has its own state
        (1.0, "RR", None, False),  # railroad is assessed by the state
        (15_000.0, "1-00", 2_142_695.0, True),  # >99% drop from a real prior value
        (30_000.0, "1-00", 2_142_695.0, False),  # a 98.6% drop is a real (if large) change
        (150.0, "1-00", 9_000.0, False),  # prior too small to call "real"
    ],
)
def test_is_nominal_assessment(total, cls, prior, expected):
    assert is_nominal_assessment(total, cls, prior_total=prior) is expected


def _dollar_parcel_summary():
    parcel = {"pin14": "14283191020000", "bldg_class": "1-00", "address": "N/A"}
    assessments = [
        {"year": "2026", "class": "100", "board_tot": "1", "board_land": "1", "board_bldg": "0"},
        {"year": "2025", "class": "100", "board_tot": "1", "board_land": "1", "board_bldg": "0"},
        {"year": "2024", "class": "100", "board_tot": "1", "mailed_tot": "2142695"},
    ]
    tax_result = {"year": 2024, "tax_code": "70023", "tax_bill_total": 0.2, "assessed_value": 1,
                  "line_items": [{"agency": "CITY OF CHICAGO", "rate": 1.0, "amount": 0.2}], "exemptions": []}
    return _build_summary(parcel, None, assessments, [], tax_result)


def test_dollar_parcel_shows_no_value_market_value_or_tax():
    s = _dollar_parcel_summary()
    assert s.nominal_assessment is True
    assert s.nominal_assessed_value == 1.0
    assert s.total_assessed_value is None
    assert s.implied_market_value is None
    assert s.estimated_annual_tax is None
    assert s.effective_tax_rate is None
    assert s.tax_breakdown == []
    # The record itself is kept: the history rows are the County's numbers.
    assert [r.total for r in s.assessment_history] == [1.0, 1.0, 1.0]


def test_drop_from_real_prior_value_is_nominal():
    parcel = {"pin14": "1", "bldg_class": "1-00"}
    assessments = [
        {"year": "2025", "class": "100", "board_tot": "12000"},
        {"year": "2024", "class": "100", "board_tot": "2142695"},
    ]
    s = _build_summary(parcel, None, assessments, [])
    assert s.nominal_assessment is True
    assert s.nominal_assessed_value == 12000.0
    assert s.total_assessed_value is None


def test_ordinary_parcel_is_unchanged():
    parcel = {"pin14": "1", "bldg_class": "2-11"}
    s = _build_summary(parcel, None, [{"year": "2025", "class": "211", "board_tot": "60000"}], [])
    assert s.nominal_assessment is False
    assert s.nominal_assessed_value is None
    assert s.total_assessed_value == 60000.0
    assert s.implied_market_value == 600000


def test_exempt_parcel_is_not_called_nominal():
    s = _build_summary({"pin14": "1", "bldg_class": "EX"}, None, [{"year": "2025", "class": "EX", "board_tot": "0"}], [])
    assert s.tax_exempt is True
    assert s.nominal_assessment is False


def test_report_does_not_recover_the_token_value_from_history():
    s = _dollar_parcel_summary()
    assert _resolve_market_value_and_tax(s) == (None, None, None)
    assert s.total_assessed_value is None
    assert s.estimated_annual_tax is None
    assert s.tax_estimate_is_fallback is False


def test_report_fallback_still_works_for_a_real_value():
    prop = PropertySummary(bldg_class="2-11", total_assessed_value=60000, assessment_level=0.10)
    _, mv, _ = _resolve_market_value_and_tax(prop)
    assert mv == 600000


def test_discovery_sort_key_skips_nominal_parcels():
    assert "total_assessed_value_sortkey" not in derive_sort_fields({"total_assessed_value": 1.0, "class": "1-00"})
    assert derive_sort_fields({"total_assessed_value": 5000.0, "class": "1-00"})["total_assessed_value_sortkey"] == 5000.0


def test_area_medians_exclude_nominal_parcels(tmp_path):
    db = tmp_path / "idx.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE parcels (pin TEXT PRIMARY KEY, lat REAL, lon REAL, attrs TEXT, regions TEXT)")
    conn.execute("CREATE TABLE meta (id INTEGER PRIMARY KEY, built_at INTEGER)")
    rows = [
        ("a", {"total_assessed_value": 1.0, "class": "1-00", "land_sqft": 143032, "land_use_class": "vacant"}),
        ("b", {"total_assessed_value": 3.0, "class": "1-00", "land_sqft": 5000, "land_use_class": "vacant"}),
        ("c", {"total_assessed_value": 50000.0, "class": "2-11", "land_sqft": 3000, "land_use_class": "residential"}),
        ("d", {"total_assessed_value": 70000.0, "class": "2-11", "land_sqft": 3000, "land_use_class": "residential"}),
    ]
    for pin, attrs in rows:
        conn.execute("INSERT INTO parcels VALUES (?,?,?,?,?)", (pin, 0, 0, json.dumps(attrs), json.dumps(["neighborhood:24"])))
    conn.commit()
    conn.close()
    stats = _scan_index(str(db))[24]
    assert stats["n_parcels"] == 4
    assert stats["n_assessed"] == 2
    assert stats["median_assessed"] == 60000.0
    assert stats["n_mv_psf"] == 2
