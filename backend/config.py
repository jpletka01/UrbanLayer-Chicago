from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    socrata_app_token: str = ""
    qdrant_url: str = "http://localhost:6333"

    router_model: str = "claude-sonnet-4-6"
    synthesizer_model: str = "claude-sonnet-4-6"
    conversation_model: str = "claude-haiku-4-5-20251001"

    router_max_tokens: int = 600
    synthesizer_max_tokens: int = 2000
    conversation_max_tokens: int = 300

    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "

    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_enabled: bool = True
    reranker_candidate_count: int = 20
    reranker_weight: float = 0.2

    keyword_boost_weight: float = 0.20

    qdrant_code_collection: str = "chicago_municipal_code"
    qdrant_zoning_collection: str = "chicago_zoning"

    socrata_base: str = "https://data.cityofchicago.org/resource"
    dataset_crime: str = "ijzp-q8t2"
    dataset_311: str = "v6vf-nfxy"
    dataset_permits: str = "ydr8-5enu"
    dataset_violations: str = "22u3-xenr"
    dataset_business: str = "uupf-x98q"
    dataset_vacant_buildings: str = "kc9i-wq85"
    dataset_food_inspections: str = "4ijn-s7e5"
    dataset_community_areas: str = "igwz-8jzy"
    dataset_iucr: str = "c7ck-438e"
    dataset_zoning: str = "p8va-airx"

    # Cook County Socrata (datacatalog.cookcountyil.gov)
    cook_county_socrata_base: str = "https://datacatalog.cookcountyil.gov/resource"
    cook_county_socrata_token: str = ""
    dataset_ccao_characteristics: str = "x54s-btds"
    dataset_ccao_assessments: str = "uzyt-m557"
    dataset_ccao_sales: str = "wvhk-k5uv"
    dataset_ccao_parcels: str = "pabr-t5kh"
    # Cook County Address Points — authoritative address→PIN map (GIS-index-independent).
    # Used by the R7 address→PIN resolver. $limit=2 so a multi-match (≥2 distinct PINs)
    # can be detected and rejected as "not confident" rather than picked arbitrarily.
    dataset_address_points: str = "78yw-iddh"
    limit_address_points: int = 2
    # Kill-switch for the R7 address→PIN resolution step. False reverts _resolve_location
    # to the pre-R7 geocode + nearest-centroid path with no redeploy.
    address_point_resolution_enabled: bool = True
    limit_ccao_characteristics: int = 1
    limit_ccao_assessments: int = 5
    limit_ccao_sales: int = 10
    # Candidate cap for the Socrata Parcel Universe bounding-box fallback
    # (_lookup_parcel_socrata). MUST exceed the parcel count inside a _BBOX_DELTA
    # box or "pick closest" is computed over an arbitrary truncated subset that may
    # not even contain the true parcel — a correctness bug that silently resolves a
    # report to a wrong neighbor. A 220m box in dense residential holds ~500-600
    # parcels; 2000 covers that with headroom. (Condo towers can still exceed it —
    # those are inherently coord-ambiguous; the fallback logs a truncation warning.)
    limit_ccao_parcels: int = 2000

    # Census Reporter API (tract-level ACS demographics)
    census_reporter_base: str = "https://api.censusreporter.org/1.0"

    # Neighborhood domain
    dataset_demographics: str = "t68z-cikk"
    dataset_socioeconomic: str = "kn9c-c2s2"
    transit_search_radius_mi: float = 2.0
    walkscore_api_key: str = ""

    # Incentives domain (Chicago Data Portal)
    dataset_tif_boundaries: str = "eejr-xtfb"
    dataset_tif_financials: str = "72uz-ikdv"
    dataset_tif_fund_analysis: str = "qm7s-3ctt"
    dataset_enterprise_zones: str = "64xf-pyvh"
    dataset_sbif: str = "etqr-sz5x"
    dataset_nof_large: str = "j7ew-b73u"
    dataset_nof_small: str = "rym7-49n8"
    limit_tif_financials: int = 5
    limit_tif_fund_analysis: int = 5
    limit_grant_programs_detail: int = 15

    dataset_aro_housing: str = "s6ha-ppgi"
    limit_aro_housing: int = 20

    crime_lag_days: int = 7

    # Per-source Socrata row caps (every query must carry a $limit guard).
    limit_crime: int = 35
    limit_311: int = 200
    limit_permits: int = 500
    limit_violations: int = 200
    limit_business: int = 500
    limit_permits_detail: int = 20
    limit_business_detail: int = 20
    limit_vacant_buildings_detail: int = 20
    limit_food_inspections_detail: int = 20

    # Map endpoint row caps (higher than chat — individual points, not aggregates).
    # These must be large enough to cover the full time_range_days window so the
    # date slider and analytics section have meaningful data. 200 crime rows in a
    # busy community area only covers ~7 days; 1000 covers ~90 days comfortably.
    limit_map_crime: int = 2500
    limit_map_311: int = 1000
    limit_map_permits: int = 500
    enable_zoning_layer: bool = True

    # How many top items each assembled summary keeps.
    top_crime_types: int = 5
    top_311_depts: int = 10
    top_311_types: int = 15
    top_permits: int = 5
    top_violations: int = 5
    top_businesses: int = 5
    top_chunks: int = 5

    data_dir: Path = PROJECT_ROOT / "ingestion" / "data"
    db_path: Path = PROJECT_ROOT / "backend" / "data" / "chicago.db"
    # The prospecting index lives on the SAME persistent volume as chicago.db (backend/data),
    # NOT in ingestion/data (which is ephemeral in the container) — so a prod-built index
    # survives redeploys instead of being wiped on the next image rebuild.
    discovery_index_path: Path = PROJECT_ROOT / "backend" / "data" / "discovery_index.db"

    message_limit: int = 10

    ptaxsim_db_path: Path = PROJECT_ROOT / "backend" / "data" / "ptaxsim.db"
    ptaxsim_enabled: bool = True

    upload_dir: Path = PROJECT_ROOT / "backend" / "data" / "uploads"
    upload_max_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    upload_allowed_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]
    upload_max_per_message: int = 3

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    enable_request_logging: bool = True

    # Auth (disabled when google_client_id is empty — local dev works without OAuth)
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = ""
    jwt_access_token_ttl: int = 900  # 15 minutes
    jwt_refresh_token_ttl: int = 604_800  # 7 days
    auth_cookie_secure: bool = False  # True in production (HTTPS)
    frontend_url: str = "http://localhost:5173"

    sentry_dsn: str = ""

    mapbox_token: str = ""
    vite_mapbox_token: str = ""

    # Report v2
    limit_comparable_sales: int = 10
    limit_address_permits: int = 20
    limit_address_violations: int = 20
    limit_nearby_construction: int = 20
    comparable_sales_radius_deg: float = 0.004
    nearby_construction_radius_deg: float = 0.00725
    comparable_sales_years: int = 3
    address_permits_years: int = 5
    address_violations_years: int = 5
    nearby_construction_months: int = 12
    zoning_extract_model: str = "claude-haiku-4-5-20251001"
    zoning_extract_max_tokens: int = 1500

    # Max concurrent PDF report generations. Each in-flight report spikes ~2.8 GB
    # (WeasyPrint layout of the ~18-page, image-embedded doc); on the 8 GB prod
    # container, stacked on the ~5 GB resident baseline (citywide discovery index +
    # ML models), even two at once OOM-kills the single uvicorn worker. Pinned to 1
    # so at most one render spike is ever in flight. The render now also runs in an
    # isolated child process (backend/report_render.py), but serializing the spikes
    # keeps total memory predictable. Reports are paid + infrequent, so a second
    # concurrent request simply queues on this semaphore.
    report_concurrency: int = 1

    # Wall-clock budget (seconds) for the isolated PDF render child. If write_pdf
    # exceeds this the parent terminates the child and the request fails cleanly,
    # rather than a hung render holding _REPORT_SEM forever. Kept under the nginx
    # /api/report proxy_read_timeout (180s) so the app errors before the proxy 504s.
    report_render_timeout_s: float = 150.0

    # Coarse virtual-memory backstop (bytes) for the render child via RLIMIT_AS.
    # NOTE: RLIMIT_AS caps *virtual* address space, which for WeasyPrint (mmapped
    # fonts/libs) runs well above its RSS — so this is deliberately generous to
    # avoid false MemoryErrors on legitimate renders. The primary OOM protection is
    # not this cap: it's the child process itself (fresh address space, fully
    # reclaimed on exit) plus oom_score_adj=1000 making the child the *preferred*
    # OOM victim. 0 disables the cap.
    report_render_rlimit_as_bytes: int = 4 * 1024 * 1024 * 1024  # 4 GiB

    # Fallback effective property-tax rate on *market value* for Chicago
    # residential parcels, applied to derive an estimated annual tax when the
    # ptaxsim bill is unavailable (so the tax row isn't all-or-nothing). ~2.1%
    # is consistent with Cook County Treasurer / Civic Federation effective-rate
    # figures for residential Chicago and the report's own mock assumption
    # (0.0218). Displayed values derived this way are labeled "estimated".
    report_fallback_tax_rate: float = 0.021

    # Stripe
    stripe_secret_key: str = ""
    stripe_public_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro_monthly: str = ""
    stripe_price_id_report: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
