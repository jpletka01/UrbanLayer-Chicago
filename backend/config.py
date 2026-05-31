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

    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = False
    reranker_candidate_count: int = 20

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
    enable_zoning_layer: bool = False

    # How many top items each assembled summary keeps.
    top_crime_types: int = 5
    top_311_depts: int = 10
    top_311_types: int = 15
    top_permits: int = 5
    top_violations: int = 5
    top_businesses: int = 5
    top_chunks: int = 5

    data_dir: Path = PROJECT_ROOT / "ingestion" / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
