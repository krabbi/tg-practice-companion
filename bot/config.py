"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    # Access control — CSV of integer Telegram user IDs, e.g. "123456789".
    # NoDecode disables pydantic-settings' JSON pre-parsing of this complex field so the
    # raw env string reaches parse_csv_ids; otherwise a bare single id ("123456789") would
    # be JSON-decoded to an int and a CSV value would fail to parse at the source level.
    allowed_user_ids: Annotated[list[int], NoDecode]

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
    # NoDecode for the same reason as allowed_user_ids: a CSV string like
    # "https://a.com,https://b.com" is not valid JSON and would raise at the source level.
    cors_origins: Annotated[list[str], NoDecode] = []

    # Media storage — path on disk where uploaded audio/images are persisted (B4)
    media_storage_dir: str = "/data/media"

    # S3-compatible object storage (Backblaze B2 / AWS-portable); all optional so the bot
    # starts without them — gateway is only constructed in web/CLI wiring (S1).
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_presign_expiry_seconds: int = 900
    media_max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Web admin Mini App URL (AC-19); empty string disables the /admin command
    web_app_url: str = ""

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_csv_ids(cls, v: Any) -> list[int]:
        """Accept a CSV string ('123,456'), a single int, a JSON-ish '[1,2]' string, or a list."""
        if isinstance(v, bool):  # bool is a subclass of int; reject it explicitly
            raise ValueError(f"Cannot parse allowed_user_ids from {v!r}")
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            items = v.strip().strip("[]").split(",")
            return [int(s.strip().strip("\"'")) for s in items if s.strip().strip("\"'")]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse allowed_user_ids from {v!r}")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept a CSV string, a JSON-ish '["a","b"]' string, or an already-parsed list."""
        if isinstance(v, str):
            items = v.strip().strip("[]").split(",")
            return [s.strip().strip("\"'") for s in items if s.strip().strip("\"'")]
        if isinstance(v, (list, tuple)):
            return list(v)
        raise ValueError(f"Cannot parse cors_origins from {v!r}")


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton Config instance (cached after first call)."""
    return Config()  # type: ignore[call-arg]
