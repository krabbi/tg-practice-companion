"""Unit tests for bot/handlers/admin.py — /admin handler (AC-19)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.config import Config
from bot.handlers.admin import create_router
from bot.i18n import DEFAULT_LANGUAGE, t

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_message() -> MagicMock:
    msg = MagicMock()
    msg.answer = AsyncMock()
    return msg


def make_config(web_app_url: str = "https://example.com/admin") -> Config:
    return Config(
        telegram_bot_token="1234567890:AABBCCDDEEFFaabbccddeeff-example",
        anthropic_api_key="sk-ant-test",
        database_url="sqlite+aiosqlite:///:memory:",
        allowed_user_ids=[123456789],
        web_app_url=web_app_url,
    )


def get_handler(router, name: str):
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    raise AssertionError(f"Handler '{name}' not found in router")


# ---------------------------------------------------------------------------
# /admin — WEB_APP_URL set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_admin_sends_webapp_button_when_url_set() -> None:
    """/admin sends a message with a web_app inline button pointing to WEB_APP_URL."""
    config = make_config(web_app_url="https://example.com/admin")
    router = create_router(config)
    handler = get_handler(router, "cmd_admin")
    msg = make_message()

    await handler(msg)

    msg.answer.assert_awaited_once()
    _, kwargs = msg.answer.call_args
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None
    rows = reply_markup.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 1
    btn = rows[0][0]
    assert btn.web_app is not None
    assert btn.web_app.url == "https://example.com/admin"
    assert btn.text == t("admin_open_button", DEFAULT_LANGUAGE)


# ---------------------------------------------------------------------------
# /admin — WEB_APP_URL empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_admin_replies_not_configured_when_url_empty() -> None:
    """/admin replies with 'not configured' when WEB_APP_URL is empty."""
    config = make_config(web_app_url="")
    router = create_router(config)
    handler = get_handler(router, "cmd_admin")
    msg = make_message()

    await handler(msg)

    msg.answer.assert_awaited_once_with(t("admin_not_configured", DEFAULT_LANGUAGE))
    # Must NOT send a keyboard
    _, kwargs = msg.answer.call_args
    assert kwargs.get("reply_markup") is None
