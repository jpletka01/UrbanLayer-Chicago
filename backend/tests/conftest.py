import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_settings():
    """Shared settings mock for retrieval/socrata tests.

    Mirrors the defaults in backend/config.py so $limit assertions and dataset
    IDs stay in one place instead of being redefined per test module.
    """
    settings = MagicMock()
    settings.socrata_base = "https://data.cityofchicago.org/resource"
    settings.socrata_app_token = "test-token"
    settings.dataset_crime = "ijzp-q8t2"
    settings.dataset_311 = "v6vf-nfxy"
    settings.dataset_permits = "ydr8-5enu"
    settings.dataset_violations = "22u3-xenr"
    settings.dataset_business = "uupf-x98q"
    settings.crime_lag_days = 7
    settings.limit_crime = 35
    settings.limit_311 = 50
    settings.limit_permits = 50
    settings.limit_violations = 50
    settings.limit_business = 100
    # Cook County / CCAO
    settings.cook_county_socrata_base = "https://datacatalog.cookcountyil.gov/resource"
    settings.cook_county_socrata_token = ""
    settings.dataset_ccao_characteristics = "x54s-btds"
    settings.dataset_ccao_assessments = "uzyt-m557"
    settings.dataset_ccao_sales = "wvhk-k5uv"
    settings.limit_ccao_characteristics = 1
    settings.limit_ccao_assessments = 5
    settings.limit_ccao_sales = 10
    # Neighborhood domain
    settings.dataset_demographics = "t68z-cikk"
    settings.transit_search_radius_mi = 2.0
    return settings
