from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr("")
    migration_database_url: SecretStr = SecretStr("")
    service_key: SecretStr = SecretStr("")
    ai_mode: Literal["simulated", "live"] = "simulated"
    ai_enabled: bool = True
    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    session_hours: int = Field(default=24, ge=1, le=48)
    session_limit: int = Field(default=500, ge=1, le=5000)
    sessions_per_hour: int = Field(default=30, ge=1, le=200)
    analyses_per_minute: int = Field(default=2, ge=1, le=10)
    attempts_per_session_day: int = Field(default=10, ge=1, le=40)
    attempts_per_environment_day: int = Field(default=40, ge=1, le=100)
    candidate_limit: int = Field(default=12, ge=5, le=30)
    context_limit: int = Field(default=4, ge=1, le=4)
    cosine_distance_limit: float = Field(default=0.45, ge=0, le=1)


@lru_cache
def settings() -> Settings:
    return Settings()
