"""The rent/sale-price trend builder's pure parts (WS4 PR4, decision Item 62). No network."""

from ingestion.build_rent_trend_artifact import change_is_significant, sale_group, sales_medians


def test_a_change_is_significant_only_beyond_the_combined_margin():
    assert change_is_significant(1500, 60, 1700, 80) is True    # 200 > 100
    assert change_is_significant(1500, 90, 1600, 90) is False   # 100 < 127
    assert change_is_significant(1500, None, 1700, 80) is None  # can't judge without a margin


def test_sale_groups_by_assessor_class():
    assert sale_group("2-11") == "two_to_six" and sale_group("212") == "two_to_six"
    assert sale_group("299") == "condo"
    assert sale_group("203") == "single_family" and sale_group("295") == "single_family"
    assert sale_group("517") is None and sale_group(None) is None


def test_sales_medians_join_by_pin10_and_keep_n():
    pin_ca = {"1431332018": "24", "1431332019": "24", "2504400090": "49"}
    sales = [
        ("14313320180000|two_to_six", 2024, 500_000.0),
        ("14313320191001|two_to_six", 2024, 700_000.0),   # a unit PIN joins through its PIN10
        ("14313320180000|two_to_six", 2025, 650_000.0),
        ("25044000900000|single_family", 2024, 210_000.0),
        ("99999999990000|condo", 2024, 1.0),               # outside the city: dropped
    ]
    out = sales_medians(sales, pin_ca)
    assert out["24"]["two_to_six"]["2024"] == {"median": 600_000, "n": 2}
    assert out["24"]["two_to_six"]["2025"] == {"median": 650_000, "n": 1}
    assert out["49"]["single_family"]["2024"]["n"] == 1
    assert set(out) == {"24", "49"}
