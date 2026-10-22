from eval.tract_confidence import report, tally
from backend.models import CensusTractDemographics


def tract(**kw) -> CensusTractDemographics:
    base = dict(tract_fips="17031831000", median_gross_rent=2435, poverty_rate=1.0, acs_period="2020–2024",
                moe={"median_gross_rent": 220.0, "poverty_rate": 2.5}, cv={"median_gross_rent": 0.055, "poverty_rate": 0.61})
    return CensusTractDemographics(**{**base, **kw})


def test_tally_counts_each_state_and_the_tracts_that_lost_a_figure():
    r = tally([tract(), tract(poverty_rate=4.6, cv={"median_gross_rent": 0.055, "poverty_rate": 0.1})])
    assert r["tracts"] == 2 and r["tracts_with_withheld"] == 1
    assert r["by_field"]["poverty_rate"]["withheld"] == 1 and r["by_field"]["poverty_rate"]["standard"] == 1
    assert r["by_field"]["median_gross_rent"]["standard"] == 2
    assert "tracts with at least one withheld figure: 1 of 2" in report(r)
