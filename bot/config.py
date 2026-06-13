"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """All runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    telegram_bot_token: str

    # AI providers
    anthropic_api_key: str
    groq_api_key: str = ""

    # Database
    database_url: str

    # Access control — CSV of integer Telegram user IDs, e.g. "123456789"
    allowed_user_ids: list[int]

    # Cost guardrails (AC-16, AC-11)
    monthly_cost_limit_usd: float = 10.0
    analysis_cost_cap_usd: float = 0.05

    # AI model pins
    llm_model: str = "claude-haiku-4-5-20251001"
    whisper_model: str = "whisper-large-v3-turbo"

    # i18n
    default_language: str = "ru"

    # Send window — half-open [send_window_start, send_window_end) in local time (AC-18)
    send_window_start: int = 6
    send_window_end: int = 22

    # Stage-2 enabler stubs — unused in Stage 1, mirroring sibling repo shape
    jwt_secret: str = ""
    cors_origins: list[str] = []

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_csv_ids(cls, v: Any) -> list[int]:
        """Accept both a CSV string ('123,456') and an already-parsed list."""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse allowed_user_ids from {v!r}")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept both a CSV string and an already-parsed list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError(f"Cannot parse cors_origins from {v!r}")


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton Config instance (cached after first call)."""
    return Config()  # type: ignore[call-arg]
