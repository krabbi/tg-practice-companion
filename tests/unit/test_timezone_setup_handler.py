"""Unit tests for bot/handlers/timezone_setup.py (AC-18).

Covers:
- /timezone enters the continent-selection FSM state
- Continent callback moves to city selection
- City callback persists IANA zone via timezone_service.set_timezone
- Invalid/unknown continent restarts the flow
- timezone_service.set_timezone failure replies with error and clears state
- /timezone returns early when from_user is None
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.timezone_setup import (
    _AMERICA_CURATED,
    _CB_CITY,
    _CB_CONTINENT,
    _TZ_MAP,
    TimezoneSetupStates,
    _city_keyboard,
    continent_keyboard,
    create_router,
)
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.timezone_service import TimezoneService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_timezone_service(user=None) -> MagicMock:
    """Return a TimezoneService mock."""
    svc = MagicMock(spec=TimezoneService)
    svc.set_timezone = AsyncMock(return_value=user)
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
    data: str = "",
    message_present: bool = True,
) -> MagicMock:
    """Build a minimal aiogram CallbackQuery mock."""
    cb = MagicMock()
    cb.answer = AsyncMock()
    cb.data = data
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


def make_fsm_context(state_value: str | None = None) -> MagicMock:
    """Return a FSMContext mock."""
    ctx = MagicMock()
    ctx.set_state = AsyncMock()
    ctx.update_data = AsyncMock()
    ctx.clear = AsyncMock()
    ctx.get_state = AsyncMock(return_value=state_value)
    return ctx


def _get_handler(router, kind: str, name: str):
    """Extract a named handler callback from the router."""
    observers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for obs in observers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    return None


# ---------------------------------------------------------------------------
# /timezone command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_timezone_sets_fsm_state() -> None:
    """/timezone sends continent keyboard and sets selecting_continent state."""
    router = create_router()
    handler = _get_handler(router, "message", "cmd_timezone")
    assert handler is not None, "cmd_timezone handler not found"

    msg = make_message(user_id=111)
    state = make_fsm_context()

    await handler(msg, state=state)

    state.set_state.assert_awaited_once_with(TimezoneSetupStates.selecting_continent)
    msg.answer.assert_awaited_once()
    args, kwargs = msg.answer.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert t("tz_pick_continent", DEFAULT_LANGUAGE) in text


@pytest.mark.asyncio
async def test_cmd_timezone_no_from_user_returns_early() -> None:
    """/timezone returns early when from_user is None."""
    router = create_router()
    handler = _get_handler(router, "message", "cmd_timezone")
    assert handler is not None

    msg = make_message(user_id=None)
    state = make_fsm_context()

    await handler(msg, state=state)

    state.set_state.assert_not_awaited()
    msg.answer.assert_not_awaited()


# ---------------------------------------------------------------------------
# Continent callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_continent_selected_moves_to_city_step() -> None:
    """Selecting a valid continent edits the message with city keyboard."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_continent_selected")
    assert handler is not None

    # Pick a continent that definitely has zones
    continent = "Europe"
    cb = make_callback(data=f"{_CB_CONTINENT}{continent}")
    state = make_fsm_context()

    await handler(cb, state=state)

    cb.answer.assert_awaited_once()
    state.set_state.assert_awaited_with(TimezoneSetupStates.selecting_city)
    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.call_args[0][0]
    assert t("tz_pick_city", DEFAULT_LANGUAGE) in text


@pytest.mark.asyncio
async def test_cb_continent_selected_invalid_continent_restarts() -> None:
    """An unknown continent resets back to continent selection."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_continent_selected")
    assert handler is not None

    cb = make_callback(data=f"{_CB_CONTINENT}NotAContinent")
    state = make_fsm_context()

    await handler(cb, state=state)

    state.set_state.assert_awaited_with(TimezoneSetupStates.selecting_continent)
    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.call_args[0][0]
    assert t("tz_invalid", DEFAULT_LANGUAGE) in text


@pytest.mark.asyncio
async def test_cb_continent_no_message_returns_early() -> None:
    """Continent callback returns early when callback.message is None."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_continent_selected")
    assert handler is not None

    cb = make_callback(data=f"{_CB_CONTINENT}Europe", message_present=False)
    state = make_fsm_context()

    await handler(cb, state=state)

    cb.answer.assert_awaited_once()
    state.set_state.assert_not_awaited()


# ---------------------------------------------------------------------------
# City callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_city_selected_persists_timezone() -> None:
    """Selecting a city calls set_timezone with the correct IANA string."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_city_selected")
    assert handler is not None

    tz = "Europe/Berlin"
    cb = make_callback(user_id=111, data=f"{_CB_CITY}{tz}")
    state = make_fsm_context()
    svc = make_timezone_service()

    await handler(cb, state=state, timezone_service=svc)

    svc.set_timezone.assert_awaited_once_with(111, tz)
    state.clear.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.call_args[0][0]
    assert tz in text
    assert t("tz_set_ok", DEFAULT_LANGUAGE).format(tz=tz) == text


@pytest.mark.asyncio
async def test_cb_city_selected_service_error_replies_error() -> None:
    """When set_timezone raises TimezoneError, handler shows error and re-attaches continent keyboard."""
    from bot.exceptions import TimezoneError

    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_city_selected")
    assert handler is not None

    tz = "Invalid/Zone"
    cb = make_callback(user_id=111, data=f"{_CB_CITY}{tz}")
    state = make_fsm_context()
    svc = MagicMock(spec=TimezoneService)
    svc.set_timezone = AsyncMock(side_effect=TimezoneError("bad tz"))

    with patch("bot.handlers.timezone_setup.logger"):
        await handler(cb, state=state, timezone_service=svc)

    state.clear.assert_not_awaited()
    cb.message.edit_text.assert_awaited_once_with(
        t("tz_set_error", DEFAULT_LANGUAGE),
        reply_markup=continent_keyboard(DEFAULT_LANGUAGE),
    )


@pytest.mark.asyncio
async def test_cb_city_selected_unexpected_error_replies_error() -> None:
    """When set_timezone raises an unexpected Exception, handler shows error and re-attaches continent keyboard."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_city_selected")
    assert handler is not None

    tz = "Europe/Berlin"
    cb = make_callback(user_id=111, data=f"{_CB_CITY}{tz}")
    state = make_fsm_context()
    svc = MagicMock(spec=TimezoneService)
    svc.set_timezone = AsyncMock(side_effect=RuntimeError("db down"))

    with patch("bot.handlers.timezone_setup.logger"):
        await handler(cb, state=state, timezone_service=svc)

    state.clear.assert_not_awaited()
    cb.message.edit_text.assert_awaited_once_with(
        t("tz_set_error", DEFAULT_LANGUAGE),
        reply_markup=continent_keyboard(DEFAULT_LANGUAGE),
    )


@pytest.mark.asyncio
async def test_cb_city_no_message_returns_early() -> None:
    """City callback returns early when callback.message is None."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_city_selected")
    assert handler is not None

    cb = make_callback(user_id=111, data=f"{_CB_CITY}Europe/Berlin", message_present=False)
    state = make_fsm_context()
    svc = make_timezone_service()

    await handler(cb, state=state, timezone_service=svc)

    cb.answer.assert_awaited_once()
    svc.set_timezone.assert_not_awaited()


# ---------------------------------------------------------------------------
# TZ map sanity
# ---------------------------------------------------------------------------


def test_tz_map_contains_europe() -> None:
    """_TZ_MAP has Europe entries including Europe/Berlin."""
    assert "Europe" in _TZ_MAP
    assert "Europe/Berlin" in _TZ_MAP["Europe"]


def test_tz_map_contains_asia() -> None:
    """_TZ_MAP has Asia entries including Asia/Tokyo."""
    assert "Asia" in _TZ_MAP
    assert "Asia/Tokyo" in _TZ_MAP["Asia"]


def test_tz_map_all_zones_have_continent_prefix() -> None:
    """Every zone in _TZ_MAP starts with its continent key."""
    for continent, zones in _TZ_MAP.items():
        for tz in zones:
            assert tz.startswith(continent + "/"), f"{tz!r} does not start with {continent!r}/"


# ---------------------------------------------------------------------------
# Americas curated keyboard
# ---------------------------------------------------------------------------


def test_america_city_keyboard_uses_curated_subset() -> None:
    """_city_keyboard('America') only includes the curated subset, not all ~169 zones."""
    kb = _city_keyboard("America")
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    # The full America list has ~169 entries; curated list is much smaller.
    assert len(all_buttons) <= len(_AMERICA_CURATED)
    # Spot-check that major cities are present.
    callback_datas = {btn.callback_data for btn in all_buttons}
    assert f"{_CB_CITY}America/New_York" in callback_datas
    assert f"{_CB_CITY}America/Sao_Paulo" in callback_datas


def test_america_curated_all_are_america_prefix() -> None:
    """All curated America zones start with 'America/'."""
    for tz in _AMERICA_CURATED:
        assert tz.startswith("America/"), f"{tz!r} does not start with 'America/'"


def test_non_america_city_keyboard_not_restricted() -> None:
    """_city_keyboard for non-America continents uses the full zone list."""
    kb = _city_keyboard("Europe")
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    # Europe has many zones; the full list is used (at least as many as _TZ_MAP has).
    assert len(all_buttons) == len(_TZ_MAP.get("Europe", []))
