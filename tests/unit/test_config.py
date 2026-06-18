"""Tests for bot/config.py — Config field parsing and defaults."""

import pytest

from bot.config import Config


def make_config(**overrides: object) -> Config:
    """Construct a Config from minimal required fields plus optional overrides."""
    base = {
        "telegram_bot_token": "9999999999:AAFakeTokenForTestingPurposesOnly",
        "anthropic_api_key": "sk-ant-fake",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "allowed_user_ids": "123456789",
    }
    base.update(overrides)
    return Config.model_validate(base)


def test_csv_single_id() -> None:
    """Parse a CSV string containing a single user ID."""
    cfg = make_config(allowed_user_ids="42")
    assert cfg.allowed_user_ids == [42]


def test_csv_multiple_ids() -> None:
    """Parse a CSV string containing multiple user IDs."""
    cfg = make_config(allowed_user_ids="1,2,3")
    assert cfg.allowed_user_ids == [1, 2, 3]


def test_csv_ids_with_spaces() -> None:
    """Strip whitespace around each ID in the CSV string."""
    cfg = make_config(allowed_user_ids=" 10 , 20 ")
    assert cfg.allowed_user_ids == [10, 20]


def test_list_ids_passthrough() -> None:
    """Accept an already-parsed list of ints."""
    cfg = make_config(allowed_user_ids=[7, 8])
    assert cfg.allowed_user_ids == [7, 8]


def test_single_int_id() -> None:
    """Accept a single bare int (mirrors a JSON-decoded scalar env value)."""
    cfg = make_config(allowed_user_ids=42)
    assert cfg.allowed_user_ids == [42]


def test_bracketed_ids_string() -> None:
    """Accept a JSON-array-ish string with surrounding brackets and spaces."""
    cfg = make_config(allowed_user_ids="[42, 43]")
    assert cfg.allowed_user_ids == [42, 43]


def test_bool_allowed_user_ids_rejected() -> None:
    """Reject a bool (a subclass of int) rather than coercing it to [True->1]."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_config(allowed_user_ids=True)


def test_invalid_allowed_user_ids_raises() -> None:
    """Raise a validation error for completely unparseable allowed_user_ids."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_config(allowed_user_ids=None)


def test_groq_api_key_defaults_empty() -> None:
    """groq_api_key defaults to an empty string when omitted."""
    cfg = make_config()
    assert cfg.groq_api_key == ""


def test_monthly_cost_limit_default() -> None:
    """monthly_cost_limit_usd defaults to 10.0."""
    cfg = make_config()
    assert cfg.monthly_cost_limit_usd == 10.0


def test_analysis_cost_cap_default() -> None:
    """analysis_cost_cap_usd defaults to 0.05."""
    cfg = make_config()
    assert cfg.analysis_cost_cap_usd == 0.05


def test_llm_model_default() -> None:
    """llm_model defaults to the pinned Haiku model string."""
    cfg = make_config()
    assert cfg.llm_model == "claude-haiku-4-5-20251001"


def test_whisper_model_default() -> None:
    """whisper_model defaults to whisper-large-v3-turbo."""
    cfg = make_config()
    assert cfg.whisper_model == "whisper-large-v3-turbo"


def test_default_language_default() -> None:
    """default_language defaults to 'ru'."""
    cfg = make_config()
    assert cfg.default_language == "ru"


def test_send_window_defaults() -> None:
    """send_window_start defaults to 6, send_window_end to 22."""
    cfg = make_config()
    assert cfg.send_window_start == 6
    assert cfg.send_window_end == 22


def test_jwt_secret_stub_default() -> None:
    """Stage-2 stub jwt_secret defaults to empty string."""
    cfg = make_config()
    assert cfg.jwt_secret == ""


def test_cors_origins_stub_default_empty_list() -> None:
    """Stage-2 stub cors_origins defaults to an empty list."""
    cfg = make_config()
    assert cfg.cors_origins == []


def test_cors_origins_csv_string() -> None:
    """cors_origins accepts a CSV string."""
    cfg = make_config(cors_origins="https://a.com,https://b.com")
    assert cfg.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_empty_string() -> None:
    """cors_origins empty string produces empty list."""
    cfg = make_config(cors_origins="")
    assert cfg.cors_origins == []


def test_cors_origins_list_passthrough() -> None:
    """cors_origins accepts an already-parsed list."""
    cfg = make_config(cors_origins=["https://x.io"])
    assert cfg.cors_origins == ["https://x.io"]


def test_cors_origins_json_array_string() -> None:
    """cors_origins accepts a JSON-array-ish string with brackets and quotes."""
    cfg = make_config(cors_origins='["https://x.io", "https://y.io"]')
    assert cfg.cors_origins == ["https://x.io", "https://y.io"]


def test_web_app_url_defaults_empty() -> None:
    """web_app_url defaults to empty string when omitted."""
    cfg = make_config()
    assert cfg.web_app_url == ""


def test_web_app_url_passthrough() -> None:
    """web_app_url accepts an HTTPS URL string."""
    cfg = make_config(web_app_url="https://admin.example.com")
    assert cfg.web_app_url == "https://admin.example.com"
