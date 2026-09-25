from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = Field(
        default=SecretStr("postgresql://investigator:change-me@database:5432/db_investigator")
    )
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_base_url: str = ""
    llm_model: str = ""
    db_statement_timeout_ms: int = Field(default=10_000, ge=100, le=120_000)
    db_max_rows: int = Field(default=200, ge=1, le=1_000)
    agent_max_iterations: int = Field(default=12, ge=1, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
