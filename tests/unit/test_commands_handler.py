"""Unit tests for bot/handlers/commands.py — /start and /help handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.commands import create_router
from bot.handlers.timezone_setup import TimezoneSetupStates
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.models.user import User
from bot.repositories.user_repository import UserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_message(user_id: int | None = 123456789) -> MagicMock:
    msg = MagicMock()
    msg.answer = AsyncMock()
    if user_id is not None:
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
    else:
        msg.from_user = None
    return msg


def make_fsm_context() -> MagicMock:
    ctx = MagicMock()
    ctx.set_state = AsyncMock()
    ctx.clear = AsyncMock()
    return ctx


def make_user_repo(timezone: str | None = "Europe/Minsk") -> MagicMock:
    """Return a UserRepository mock whose get_by_telegram_id returns a user with the given tz."""
    repo = MagicMock(spec=UserRepository)
    if timezone is not None or timezone is None:
        user = MagicMock(spec=User)
        user.timezone = timezone
        repo.get_by_telegram_id = AsyncMock(return_value=user)
    return repo


def get_handler(router, name: str):
    """Return the inner handler function with the given __name__ from the router."""
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    raise AssertionError(f"Handler '{name}' not found in router")


# ---------------------------------------------------------------------------
# /start — timezone already set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_start_replies_with_welcome_when_timezone_set() -> None:
    """cmd_start sends the localised welcome message when the user already has a timezone."""
    router = create_router()
    handler = get_handler(router, "cmd_start")
    msg = make_message()
    state = make_fsm_context()
    user_repo = make_user_repo(timezone="Europe/Minsk")

    await handler(msg, state=state, user_repo=user_repo)

    msg.answer.assert_awaited_once_with(t("start_welcome", DEFAULT_LANGUAGE))
    state.set_state.assert_not_awaited()


# ---------------------------------------------------------------------------
# /start — first run (timezone is None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_start_enters_timezone_picker_when_timezone_unset() -> None:
    """cmd_start redirects into the timezone picker when user.timezone is None."""
    router = create_router()
    handler = get_handler(router, "cmd_start")
    msg = make_message()
    state = make_fsm_context()
    user_repo = make_user_repo(timezone=None)

    await handler(msg, state=state, user_repo=user_repo)

    state.set_state.assert_awaited_once_with(TimezoneSetupStates.selecting_continent)
    msg.answer.assert_awaited_once()
    args, kwargs = msg.answer.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert t("tz_pick_continent", DEFAULT_LANGUAGE) in text
    # Must NOT send the welcome message on first run
    assert t("start_welcome", DEFAULT_LANGUAGE) not in text


@pytest.mark.asyncio
async def test_cmd_start_sends_welcome_when_user_not_found() -> None:
    """cmd_start sends the welcome if the user row does not exist yet (None from repo)."""
    router = create_router()
    handler = get_handler(router, "cmd_start")
    msg = make_message()
    state = make_fsm_context()
    user_repo = MagicMock(spec=UserRepository)
    user_repo.get_by_telegram_id = AsyncMock(return_value=None)

    await handler(msg, state=state, user_repo=user_repo)

    msg.answer.assert_awaited_once_with(t("start_welcome", DEFAULT_LANGUAGE))
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_start_returns_early_when_no_from_user() -> None:
    """cmd_start returns early when from_user is None."""
    router = create_router()
    handler = get_handler(router, "cmd_start")
    msg = make_message(user_id=None)
    state = make_fsm_context()
    user_repo = MagicMock(spec=UserRepository)
    user_repo.get_by_telegram_id = AsyncMock(return_value=None)

    await handler(msg, state=state, user_repo=user_repo)

    msg.answer.assert_not_awaited()
    state.set_state.assert_not_awaited()
    user_repo.get_by_telegram_id.assert_not_awaited()


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_help_replies_with_help_text() -> None:
    """cmd_help sends the localised help text."""
    router = create_router()
    handler = get_handler(router, "cmd_help")
    msg = make_message()

    await handler(msg)

    msg.answer.assert_awaited_once_with(t("help_text", DEFAULT_LANGUAGE))
