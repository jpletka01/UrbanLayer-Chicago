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

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_query_prefix: str = ""

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

    data_dir: Path = PROJECT_ROOT / "ingestion" / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
