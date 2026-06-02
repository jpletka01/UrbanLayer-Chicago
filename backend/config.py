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

    anthropic_api_key: str
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

    keyword_boost_weight: float = 0.15

    qdrant_code_collection: str = "chicago_municipal_code"
    qdrant_zoning_collection: str = "chicago_zoning"

    socrata_base: str = "https://data.cityofchicago.org/resource"
    dataset_crime: str = "ijzp-q8t2"
    dataset_311: str = "v6vf-nfxy"
    dataset_permits: str = "ydr8-5enu"
    dataset_violations: str = "22u3-xenr"
    dataset_business: str = "uupf-x98q"
    dataset_community_areas: str = "igwz-8jzy"
    dataset_iucr: str = "c7ck-438e"
    dataset_zoning: str = "p8va-airx"

    # Cook County Socrata (datacatalog.cookcountyil.gov)
    cook_county_socrata_base: str = "https://datacatalog.cookcountyil.gov/resource"
    cook_county_socrata_token: str = ""
    dataset_ccao_characteristics: str = "x54s-btds"
    dataset_ccao_assessments: str = "uzyt-m557"
    dataset_ccao_sales: str = "wvhk-k5uv"
    limit_ccao_characteristics: int = 1
    limit_ccao_assessments: int = 5
    limit_ccao_sales: int = 10

    # Neighborhood domain
    dataset_demographics: str = "t68z-cikk"
    dataset_socioeconomic: str = "kn9c-c2s2"
    transit_search_radius_mi: float = 2.0
    walkscore_api_key: str = ""

    # Incentives domain (Chicago Data Portal)
    dataset_tif_boundaries: str = "eejr-xtfb"
    dataset_tif_financials: str = "72uz-ikdv"
    dataset_enterprise_zones: str = "64xf-pyvh"
    limit_tif_financials: int = 5

    crime_lag_days: int = 7

    # Per-source Socrata row caps (every query must carry a $limit guard).
    limit_crime: int = 35
    limit_311: int = 50
    limit_permits: int = 500
    limit_violations: int = 50
    limit_business: int = 100

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
