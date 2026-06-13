"""Unit tests for bot/handlers/skip_day.py (AC-5).

Covers:
- cmd_skip_day happy path: replies localised confirmation with date
- cmd_skip_day error path: service raises → logs + localised error reply
- cmd_skip_day guard: message.from_user is None → early return, no service call
- cb_skip_today happy path: edits message with confirmation
- cb_skip_today error path: service raises → edits message with error string
- cb_skip_today guard: callback.from_user / callback.message is None → early return
- skip_today_keyboard: returns InlineKeyboardMarkup with correct callback_data
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.skip_day import _CALLBACK_SKIP_TODAY, create_router, skip_today_keyboard
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.skip_day_service import SkipDayService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skip_service(return_date: date = date(2026, 6, 12)) -> MagicMock:
    """Return a SkipDayService mock that returns the given date."""
    svc = MagicMock(spec=SkipDayService)
    svc.skip_today = AsyncMock(return_value=return_date)
    return svc


def make_message(user_id: int | None = 123456789) -> MagicMock:
    """Build a minimal aiogram Message mock."""
    msg = MagicMock()
    msg.answer = AsyncMock()
    if user_id is not None:
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
    else:
        msg.from_user = None
    return msg


def make_callback(
    user_id: int | None = 123456789,
    message_present: bool = True,
) -> MagicMock:
    """Build a minimal aiogram CallbackQuery mock."""
    cb = MagicMock()
    cb.answer = AsyncMock()
    if user_id is not None:
        cb.from_user = MagicMock()
        cb.from_user.id = user_id
    else:
        cb.from_user = None

    if message_present:
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
    else:
        cb.message = None
    return cb


# ---------------------------------------------------------------------------
# cmd_skip_day
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_skip_day_happy_path() -> None:
    """cmd_skip_day sends localised confirmation containing the date."""
    router = create_router()
    # Pull the inner handler from the router's registered observers
    # We call it directly to keep tests independent of aiogram routing internals.
    # The handler is the first message observer registered on the router.
    handler_func = None
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cmd_skip_day":
            handler_func = obs.callback
            break

    assert handler_func is not None, "cmd_skip_day handler not found in router"

    skip_date = date(2026, 6, 12)
    svc = make_skip_service(return_date=skip_date)
    msg = make_message(user_id=123456789)

    await handler_func(msg, skip_day_service=svc)

    svc.skip_today.assert_awaited_once_with(123456789)
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.call_args[0][0]
    assert skip_date.isoformat() in sent_text
    assert t("skip_day_confirmed", DEFAULT_LANGUAGE).format(date=skip_date.isoformat()) == sent_text


@pytest.mark.asyncio
async def test_cmd_skip_day_error_path() -> None:
    """cmd_skip_day replies with localised error when service raises."""
    router = create_router()
    handler_func = None
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cmd_skip_day":
            handler_func = obs.callback
            break

    assert handler_func is not None

    svc = MagicMock(spec=SkipDayService)
    svc.skip_today = AsyncMock(side_effect=RuntimeError("DB failure"))
    msg = make_message(user_id=123456789)

    with patch("bot.handlers.skip_day.logger") as mock_logger:
        await handler_func(msg, skip_day_service=svc)

    mock_logger.exception.assert_called_once()
    msg.answer.assert_awaited_once_with(t("skip_day_error", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_skip_day_no_from_user_returns_early() -> None:
    """cmd_skip_day returns early when message.from_user is None."""
    router = create_router()
    handler_func = None
    for obs in router.message.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cmd_skip_day":
            handler_func = obs.callback
            break

    assert handler_func is not None

    svc = make_skip_service()
    msg = make_message(user_id=None)

    await handler_func(msg, skip_day_service=svc)

    svc.skip_today.assert_not_awaited()
    msg.answer.assert_not_awaited()


# ---------------------------------------------------------------------------
# cb_skip_today
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_skip_today_happy_path() -> None:
    """cb_skip_today edits message with localised confirmation."""
    router = create_router()
    handler_func = None
    for obs in router.callback_query.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cb_skip_today":
            handler_func = obs.callback
            break

    assert handler_func is not None, "cb_skip_today handler not found in router"

    skip_date = date(2026, 6, 12)
    svc = make_skip_service(return_date=skip_date)
    cb = make_callback(user_id=123456789, message_present=True)

    await handler_func(cb, skip_day_service=svc)

    cb.answer.assert_awaited_once()
    svc.skip_today.assert_awaited_once_with(123456789)
    cb.message.edit_text.assert_awaited_once()
    sent_text = cb.message.edit_text.call_args[0][0]
    assert skip_date.isoformat() in sent_text


@pytest.mark.asyncio
async def test_cb_skip_today_error_path() -> None:
    """cb_skip_today edits message with localised error when service raises."""
    router = create_router()
    handler_func = None
    for obs in router.callback_query.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cb_skip_today":
            handler_func = obs.callback
            break

    assert handler_func is not None

    svc = MagicMock(spec=SkipDayService)
    svc.skip_today = AsyncMock(side_effect=RuntimeError("DB failure"))
    cb = make_callback(user_id=123456789, message_present=True)

    with patch("bot.handlers.skip_day.logger") as mock_logger:
        await handler_func(cb, skip_day_service=svc)

    mock_logger.exception.assert_called_once()
    cb.message.edit_text.assert_awaited_once_with(t("skip_day_error", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cb_skip_today_no_from_user_returns_early() -> None:
    """cb_skip_today returns early when callback.from_user is None."""
    router = create_router()
    handler_func = None
    for obs in router.callback_query.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cb_skip_today":
            handler_func = obs.callback
            break

    assert handler_func is not None

    svc = make_skip_service()
    cb = make_callback(user_id=None, message_present=True)

    await handler_func(cb, skip_day_service=svc)

    # answer() is called before the guard, so it fires even when from_user is None
    cb.answer.assert_awaited_once()
    svc.skip_today.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_skip_today_no_message_returns_early() -> None:
    """cb_skip_today returns early when callback.message is None."""
    router = create_router()
    handler_func = None
    for obs in router.callback_query.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == "cb_skip_today":
            handler_func = obs.callback
            break

    assert handler_func is not None

    svc = make_skip_service()
    cb = make_callback(user_id=123456789, message_present=False)

    await handler_func(cb, skip_day_service=svc)

    cb.answer.assert_awaited_once()
    svc.skip_today.assert_not_awaited()


# ---------------------------------------------------------------------------
# skip_today_keyboard
# ---------------------------------------------------------------------------


def test_skip_today_keyboard_structure() -> None:
    """skip_today_keyboard returns a keyboard with the correct callback_data."""
    kb = skip_today_keyboard()
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) == 1
    btn = row[0]
    assert btn.callback_data == _CALLBACK_SKIP_TODAY
    assert btn.text == t("skip_day_button", DEFAULT_LANGUAGE)
