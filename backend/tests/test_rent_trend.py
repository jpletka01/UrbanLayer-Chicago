"""Serving the rent and sale-price trends from the committed artifact (WS4 PR4, decision Item 62)."""

import pytest

from backend.retrieval.neighborhood import rent


@pytest.fixture(autouse=True)
def _fresh():
    rent.reset_artifact()
    yield
    rent.reset_artifact()


def test_west_town_rent_trend_reads_both_periods_and_the_test():
    tr = rent.rent_trend(24)
    assert tr.earlier.period == "2015–2019" and tr.later.period == "2020–2024"
    assert tr.later.median > tr.earlier.median
    assert tr.real_change_pct < tr.change_pct  # inflation is taken out
    assert tr.significant in (True, False)


def test_sales_trend_lists_every_year_for_each_group_with_n():
    st = rent.sales_trend(24)
    assert st.years == [str(y) for y in range(int(st.years[0]), int(st.years[-1]) + 1)]
    assert set(st.groups) <= {"single_family", "two_to_six", "condo"}
    for cells in st.groups.values():
        assert [c.year for c in cells] == st.years  # a year with no sales is n = 0, never skipped


def test_an_unknown_area_has_no_trend():
    assert rent.rent_trend(999) is None and rent.sales_trend(999) is None
