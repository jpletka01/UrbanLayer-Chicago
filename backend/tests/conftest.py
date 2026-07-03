import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.retrieval.cache import TTLCache


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
    settings.limit_311 = 200
    settings.limit_permits = 500
    settings.limit_violations = 200
    settings.limit_business = 500
    settings.limit_permits_detail = 20
    settings.limit_business_detail = 20
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
    settings.dataset_socioeconomic = "kn9c-c2s2"
    settings.transit_search_radius_mi = 2.0
    return settings


@pytest.fixture(autouse=True)
def _clear_ttl_caches():
    """Clear all TTLCache instances before each test to prevent cross-test pollution."""
    for instance in TTLCache._instances:
        instance._store.clear()
    yield
    for instance in TTLCache._instances:
        instance._store.clear()


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters between tests."""
    from backend.rate_limit import clear_rate_limits
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture(autouse=True)
def _no_external_property_fallbacks(request):
    """Neutralize the property orchestrator's phase-2 lookups in unit tests.

    `property_domain` calls the parcel-geometry lookup (opens the real 9.4 GB
    ptaxsim.db) and, when characteristics are absent, the building-fact
    fallbacks (real Socrata calls with retry/backoff — these HUNG the suite,
    same class as the documented estimate_tax gotcha). The orchestrator imports
    them at call time, so patching the source-module attributes covers every
    orchestrator-level test; test_parcel_geometry / test_building_facts hold
    direct references from module-top imports and are unaffected.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return
    with (
        patch("backend.retrieval.property.parcel_geometry.get_parcel_geometry_facts",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.building_facts.get_condo_characteristics",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.building_facts.get_commercial_building_sqft",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.building_facts.get_footprint_facts",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.energy.get_energy_benchmark",
              new=AsyncMock(return_value=None)),
        # Same class of gotcha on the neighborhood side: the traffic-counts
        # lookup is imported at call time by neighborhood_domain and would
        # otherwise hit the network (with retry/backoff) in orchestrator tests.
        patch("backend.retrieval.neighborhood.traffic.get_traffic_context",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.appeals.get_appeals",
              new=AsyncMock(return_value=None)),
        patch("backend.retrieval.property.parcel_flags.get_parcel_flags",
              new=AsyncMock(return_value=None)),
    ):
        yield
