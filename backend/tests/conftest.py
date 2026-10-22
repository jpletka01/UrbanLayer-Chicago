import socket

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
    settings.limit_violations = 200
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
    settings.transit_search_radius_mi = 2.0
    return settings


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    """Fail any unit test that tries to open a network connection.

    Retrieval code degrades gracefully by design (a failed source becomes a
    partial result), so a test that forgot to mock a data source used to pass
    anyway while making real Socrata calls with retries, or connecting to
    whatever Qdrant happened to be running locally. Blocking connects and DNS
    here, and failing on any attempt, keeps the unit suite hermetic and fast.
    Tests marked `integration` are exempt.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return
    attempts: list[str] = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _blocked(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(f"connect {address}")
            raise OSError(f"network access blocked in unit tests: {address}")
        return None

    def connect(sock, address):
        _blocked(sock, address)
        return real_connect(sock, address)

    def connect_ex(sock, address):
        _blocked(sock, address)
        return real_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        attempts.append(f"resolve {host}")
        raise socket.gaierror(f"network access blocked in unit tests: {host}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
    if attempts:
        pytest.fail(f"unit test attempted network access (mock it): {sorted(set(attempts))}")


@pytest.fixture(autouse=True)
def _clear_ttl_caches():
    """Clear all TTLCache instances before each test to prevent cross-test pollution."""
    for instance in TTLCache._instances:
        instance._store.clear()
    yield
    for instance in TTLCache._instances:
        instance._store.clear()


@pytest.fixture(autouse=True)
def _no_legislation_snapshot(tmp_path, monkeypatch):
    """The app reads the daily legislation sync's snapshot from backend/data, which
    differs per machine (absent in CI, whatever the last sync wrote locally). Point it
    at a missing file so every test starts "never checked"; a test that needs one
    writes it there (see test_legislation_currency.py)."""
    from backend.legislation import currency

    monkeypatch.setattr(currency, "SNAPSHOT_FILE", tmp_path / "legislation_snapshot.json")


@pytest.fixture(autouse=True)
def _no_data_health_store(tmp_path, monkeypatch):
    """Provenance reads source dates from the data-health store, which differs per machine
    (absent in CI, whatever the last check wrote locally). Point it at a missing file; a test
    that needs a store writes one there (see test_provenance_figures.py)."""
    from backend.data_health import status

    monkeypatch.setattr(status, "DB_FILE", tmp_path / "data_health.db")
    status.reset_cache()


@pytest.fixture(autouse=True)
def _no_live_failures(tmp_path, monkeypatch):
    """Live call counts are per process and the live-failure file differs per machine; every test starts
    with neither, and no test can be told a source is failing by a leftover dev file."""
    from backend.data_health import live

    monkeypatch.setattr(live, "DB_FILE", tmp_path / "data_health_live.db")
    monkeypatch.delenv("DATA_HEALTH_FAULT", raising=False)
    live.reset()
    yield
    live.reset()


@pytest.fixture(autouse=True)
def _no_indexed_sections():
    """``article_id`` reads the code index's article ids, registered when vector_search
    first scrolls Qdrant. Start each test unregistered (the hundreds fallback); a test
    that needs the index uses ``indexed_code``."""
    from backend.code_sections import set_indexed_sections
    set_indexed_sections(())
    yield
    set_indexed_sections(())


# Article ids as the 2026-06-17 index holds them (ingestion/data/chunks.jsonl): chapter
# 17-7 starts articles off the hundred (0450, 0510 … 0590); Title 11 numbers sections 1010….
INDEXED_ARTICLES = (
    "17-2-0100", "17-2-0200", "17-2-0300", "17-2-0400", "17-3-0400", "17-3-0500",
    "17-7-0100", "17-7-0200", "17-7-0300", "17-7-0400", "17-7-0450", "17-7-0500", "17-7-0510", "17-7-0550",
    "17-7-0560", "17-7-0570", "17-7-0580", "17-7-0590", "17-7-0600", "17-7-0700",
    "17-11-0050", "17-11-0100", "11-4-1010", "11-4-1020", "2-120-740", "14A-4-407",
)


@pytest.fixture
def indexed_code():
    from backend.code_sections import set_indexed_sections
    set_indexed_sections(INDEXED_ARTICLES)
    return INDEXED_ARTICLES


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
        patch("backend.retrieval.property.building_facts.get_commercial_facts",
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
