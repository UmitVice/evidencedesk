from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("")
    migration_database_url: SecretStr = SecretStr("")
    # Local maintainer reports only (`cli review-report`); never set on the hosted API.
    review_database_url: SecretStr = SecretStr("")
    service_key: SecretStr = SecretStr("")
    ai_mode: Literal["simulated", "live"] = "simulated"
    ai_enabled: bool = True
    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    # Generation can move to hosted OpenAI (GPT-6 Luna by default) or a self-hosted
    # OpenAI-compatible server (for example llama.cpp serving the fine-tuned Gemma model);
    # embeddings always stay on the live manifest.
    embedding_provider: Literal["cloudflare", "local"] = "cloudflare"
    generation_provider: Literal["cloudflare", "openai", "openai_compatible"] = "cloudflare"
    generation_base_url: str = ""
    generation_model: str = ""
    generation_api_key: SecretStr = SecretStr("")
    generation_timeout_seconds: float = Field(default=30, ge=1, le=120)
    generation_json_schema: bool = True
    generation_disable_thinking: bool = True
    generation_fallback: bool = True
    analysis_deadline_seconds: int = Field(default=40, ge=30, le=180)
    session_hours: int = Field(default=24, ge=1, le=48)
    session_limit: int = Field(default=500, ge=1, le=5000)
    sessions_per_hour: int = Field(default=30, ge=1, le=200)
    analyses_per_minute: int = Field(default=2, ge=1, le=10)
    attempts_per_session_day: int = Field(default=10, ge=1, le=40)
    attempts_per_environment_day: int = Field(default=40, ge=1, le=100)
    candidate_limit: int = Field(default=12, ge=5, le=30)
    context_limit: int = Field(default=4, ge=1, le=4)
    cosine_distance_limit: float = Field(default=0.45, ge=0, le=1)
    # One-hop document graph expansion after rank fusion (see evidencedesk.graph).
    graph_expansion: bool = False


@lru_cache
def settings() -> Settings:
    return Settings()
