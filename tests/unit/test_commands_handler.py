"""Unit tests for bot/handlers/commands.py — /start and /help handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.commands import create_router
from bot.i18n import DEFAULT_LANGUAGE, t

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_message() -> MagicMock:
    msg = MagicMock()
    msg.answer = AsyncMock()
    return msg


def get_handler(router, name: str):
    """Return the inner handler function with the given __name__ from the router."""
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    raise AssertionError(f"Handler '{name}' not found in router")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_start_replies_with_welcome() -> None:
    """cmd_start sends the localised welcome message."""
    router = create_router()
    handler = get_handler(router, "cmd_start")
    msg = make_message()

    await handler(msg)

    msg.answer.assert_awaited_once_with(t("start_welcome", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_help_replies_with_help_text() -> None:
    """cmd_help sends the localised help text."""
    router = create_router()
    handler = get_handler(router, "cmd_help")
    msg = make_message()

    await handler(msg)

    msg.answer.assert_awaited_once_with(t("help_text", DEFAULT_LANGUAGE))
