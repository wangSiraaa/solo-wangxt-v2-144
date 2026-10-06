"""Runtime configuration.

All services run locally. Override via environment variables (see .env.example).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IREVAL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://ir@127.0.0.1:5432/ireval"
    opensearch_hosts: str = "http://127.0.0.1:9200"
    opensearch_verify_certs: bool = False
    # A run never retrieves more than this many hits; recall denominator must be
    # interpreted relative to this cutoff as well as the judged set.
    max_fetch: int = 100
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
