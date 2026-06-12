"""Bootstrap conftest — self-contained while bot/ has no real modules.

`fake_config` is a stub defined here on purpose: importing `bot.config` or
`bot.models.base` (the sibling-project pattern) would crash pytest collection
with ImportError on the greenfield tree, before any bootstrap bypass runs.

Once `bot/config.py` lands (M0), replace `_StubConfig` with the real `Config`
and add the `db_session` fixture (aiosqlite ``:memory:``) next to the first
models. See `.claude/testing-guide.md`.
"""

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class _StubConfig:
    """Field names mirror the planned bot.config.Config (see issue M0)."""

    telegram_bot_token: str = "1234567890:AAFakeTokenForTestingPurposesOnly"
    anthropic_api_key: str = "sk-ant-fake-key-for-testing"
    groq_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///:memory:"
    allowed_user_ids: tuple[int, ...] = (123456789,)
    monthly_cost_limit_usd: float = 10.0
    analysis_cost_cap_usd: float = 0.05
    default_language: str = "ru"
    send_window_start: int = 6
    send_window_end: int = 22


@pytest.fixture
def fake_config() -> _StubConfig:
    """Return a credentials-free config stub for unit tests."""
    return _StubConfig()
