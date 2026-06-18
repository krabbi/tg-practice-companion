"""Unit tests for bot/middlewares/dependency.py.

Covers:
- __call__ builds all services/repos and injects them into data{}
- handler receives all expected keys in data
- session context manager is used (opened and closed)
- DeliveryService receives the bot from data["event_bot"] when data["bot"] is absent
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.middlewares.dependency import DependencyMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_middleware() -> tuple[DependencyMiddleware, MagicMock]:
    """Return (middleware, mock_session_factory)."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    config = MagicMock()
    mw = DependencyMiddleware(session_factory=mock_factory, config=config)
    return mw, mock_factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_injects_all_expected_keys() -> None:
    """__call__ must inject skip_day_service, timezone_service, practice_service,
    delivery_service, user_repo, practice_repo, send_repo into data{}."""
    mw, mock_factory = make_middleware()

    captured_data: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> str:
        captured_data.update(data)
        return "ok"

    event = MagicMock()
    data: dict[str, Any] = {}

    with (
        patch("bot.middlewares.dependency.UserRepository"),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService"),
    ):
        result = await mw(handler, event, data)

    assert result == "ok"
    for key in (
        "skip_day_service",
        "timezone_service",
        "practice_service",
        "delivery_service",
        "user_repo",
        "practice_repo",
        "send_repo",
    ):
        assert key in captured_data, f"expected key '{key}' missing from data"


@pytest.mark.asyncio
async def test_call_opens_session_context_manager() -> None:
    """__call__ must open and close the session via async context manager."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    config = MagicMock()
    mw = DependencyMiddleware(session_factory=mock_factory, config=config)

    async def handler(event: Any, data: dict[str, Any]) -> None:
        pass

    with (
        patch("bot.middlewares.dependency.UserRepository"),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService"),
    ):
        await mw(handler, MagicMock(), {})

    mock_session.__aenter__.assert_awaited_once()
    mock_session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_returns_handler_return_value() -> None:
    """__call__ must return whatever the inner handler returns."""
    mw, _ = make_middleware()

    async def handler(event: Any, data: dict[str, Any]) -> int:
        return 42

    with (
        patch("bot.middlewares.dependency.UserRepository"),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService"),
    ):
        result = await mw(handler, MagicMock(), {})

    assert result == 42


@pytest.mark.asyncio
async def test_provisioning_calls_get_or_create_when_event_user_present() -> None:
    """DependencyMiddleware calls user_repo.get_or_create when event_from_user is present."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)

    config = MagicMock()
    config.default_language = "ru"
    config.groq_api_key = ""
    mw = DependencyMiddleware(session_factory=mock_factory, config=config)

    user_mock = MagicMock()
    user_mock.id = 42

    mock_user_repo_instance = MagicMock()
    mock_user_repo_instance.get_or_create = AsyncMock(return_value=MagicMock())

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    with (
        patch("bot.middlewares.dependency.UserRepository", return_value=mock_user_repo_instance),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService"),
    ):
        result = await mw(handler, MagicMock(), {"event_from_user": user_mock})

    assert result == "ok"
    mock_user_repo_instance.get_or_create.assert_awaited_once_with(42, language="ru")
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provisioning_skipped_when_no_event_user() -> None:
    """DependencyMiddleware skips provisioning when event_from_user is absent."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)

    config = MagicMock()
    config.default_language = "ru"
    config.groq_api_key = ""
    mw = DependencyMiddleware(session_factory=mock_factory, config=config)

    mock_user_repo_instance = MagicMock()
    mock_user_repo_instance.get_or_create = AsyncMock(return_value=MagicMock())

    async def handler(event: Any, data: dict[str, Any]) -> str:
        return "ok"

    with (
        patch("bot.middlewares.dependency.UserRepository", return_value=mock_user_repo_instance),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService"),
    ):
        result = await mw(handler, MagicMock(), {})

    assert result == "ok"
    mock_user_repo_instance.get_or_create.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delivery_service_gets_event_bot_when_bot_absent() -> None:
    """When data has no 'bot' key, DeliveryService must be built with event_bot."""
    mw, _ = make_middleware()

    mock_event_bot = MagicMock()
    mock_event_bot.name = "event_bot"
    delivery_calls: list[Any] = []

    async def handler(event: Any, data: dict[str, Any]) -> None:
        pass

    with (
        patch("bot.middlewares.dependency.UserRepository"),
        patch("bot.middlewares.dependency.PracticeRepository"),
        patch("bot.middlewares.dependency.PracticeSendRepository"),
        patch("bot.middlewares.dependency.SkipDayService"),
        patch("bot.middlewares.dependency.TimezoneService"),
        patch("bot.middlewares.dependency.PracticeService"),
        patch("bot.middlewares.dependency.DeliveryService") as mock_delivery_cls,
    ):
        await mw(handler, MagicMock(), {"event_bot": mock_event_bot})
        delivery_calls = mock_delivery_cls.call_args_list

    assert len(delivery_calls) == 1
    # The first positional arg to DeliveryService() should be the event_bot
    passed_bot = delivery_calls[0][0][0]
    assert passed_bot is mock_event_bot
