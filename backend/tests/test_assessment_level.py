"""Class-aware assessment levels — the 4520 N Clark regression.

A class-5 commercial parcel assesses at 25% of market value; deriving market
value (and the effective tax rate) through the residential 10% level
overstated market 2.5× and understated the rate 2.5× (shown 2.06%, true
~5.15% on the live parcel that surfaced this).
"""

import pytest

from backend.main import _resolve_market_value_and_tax
from backend.models import PropertySummary
from backend.retrieval.property.assessment_level import assessment_level_for_class


@pytest.mark.parametrize(
    "bldg_class,level",
    [
        ("100", 0.10),   # vacant
        ("203", 0.10),   # residential
        ("2-11", 0.10),  # dash-formatted residential
        ("318", 0.10),   # multifamily
        ("4-17", 0.20),  # not-for-profit
        ("517", 0.25),   # commercial (the 4520 N Clark class)
        ("593", 0.25),
        ("663", 0.10),   # incentive 6b
        ("716", 0.10),   # incentive 7
        ("837", 0.10),   # incentive 8
        ("EX", None),    # exempt — no market-value derivation
        ("RR", None),    # railroad
        (None, None),
        ("", None),
    ],
)
def test_assessment_level_for_class(bldg_class, level):
    assert assessment_level_for_class(bldg_class) == level


def test_commercial_market_value_uses_25pct_level():
    # 4520 N Clark St (PIN 14171130250000): class 517, AV $248,427,
    # ptaxsim bill $51,178.56. Market must be ~$994K, not $2.48M.
    prop = PropertySummary(
        pin14="14171130250000",
        bldg_class="517",
        assessment_level=0.25,
        total_assessed_value=248427,
        estimated_annual_tax=51178.56,
    )
    rate, mv, level = _resolve_market_value_and_tax(prop)
    assert level == 0.25
    assert mv == round(248427 / 0.25)  # 993_708
    assert rate == round(51178.56 / 993708, 4)  # ~0.0515, not 0.0206


def test_commercial_level_derived_from_class_when_unset():
    # Safety net: a PropertySummary built without the precomputed level (mock
    # paths, older fixtures) still resolves through its class.
    prop = PropertySummary(
        pin14="1",
        bldg_class="517",
        total_assessed_value=100000,
        estimated_annual_tax=20000,
    )
    rate, mv, level = _resolve_market_value_and_tax(prop)
    assert level == 0.25
    assert mv == 400000


def test_build_summary_populates_class_aware_tax_fields():
    from backend.retrieval.property import _build_summary

    parcel = {"pin14": "14171130250000", "bldg_class": "517",
              "address": "4520 N CLARK ST"}
    assessments = [
        {"year": "2026", "class": "517", "mailed_tot": "248427"},
    ]
    tax_result = {
        "year": 2024,
        "tax_code": "73064",
        "tax_bill_total": 51178.56,
        "line_items": [],
        "exemptions": [],
    }
    s = _build_summary(parcel, None, assessments, [], tax_result)
    assert s.assessment_level == 0.25
    assert s.implied_market_value == round(248427 / 0.25)
    assert s.effective_tax_rate == round(51178.56 / round(248427 / 0.25), 4)
    assert s.tax_year == 2024


def test_build_summary_exempt_class_has_no_derived_market_value():
    from backend.retrieval.property import _build_summary

    parcel = {"pin14": "1", "bldg_class": "EX"}
    s = _build_summary(parcel, None, [], [])
    assert s.tax_exempt is True
    assert s.assessment_level is None
    assert s.implied_market_value is None
    assert s.effective_tax_rate is None


def test_unknown_class_falls_back_to_residential_level():
    prop = PropertySummary(
        pin14="1",
        total_assessed_value=114600,
        estimated_annual_tax=23024,
    )
    rate, mv, level = _resolve_market_value_and_tax(prop)
    assert level == 0.10
    assert mv == 1146000
