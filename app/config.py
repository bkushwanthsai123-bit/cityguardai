"""Application configuration via pydantic-settings (reads .env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, overridable via environment or .env file."""

    DB_URL: str = "sqlite:///./smartcity.db"
    MODEL_PATH: str = "ml/weights/best.pt"
    OLLAMA_HOST: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.1:8b"
    LLM_PROVIDER: str = "ollama"
    CONF_THRESHOLD: float = 0.25
    UPLOAD_DIR: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Module-level singleton for convenient imports.
settings = get_settings()
