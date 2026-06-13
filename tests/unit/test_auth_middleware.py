"""Tests for bot/middlewares/auth.py — whitelist enforcement."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.middlewares.auth import AuthMiddleware


def make_middleware(allowed: list[int] | None = None) -> AuthMiddleware:
    """Return an AuthMiddleware with the given allowed IDs (default: [42])."""
    return AuthMiddleware(allowed if allowed is not None else [42])


def make_update_data(user_id: int | None) -> dict[str, Any]:
    """Build a minimal aiogram data dict simulating an update from user_id."""
    from aiogram.types import Update, User

    update = MagicMock(spec=Update)
    update.update_id = 1

    if user_id is not None:
        user = MagicMock(spec=User)
        user.id = user_id
        return {"event_update": update, "event_from_user": user}
    else:
        return {"event_update": update, "event_from_user": None}


@pytest.mark.asyncio
async def test_allows_whitelisted_user() -> None:
    """Pass the update through when sender is in the whitelist."""
    middleware = make_middleware(allowed=[42])
    handler = AsyncMock(return_value="ok")
    event = MagicMock()
    data = make_update_data(user_id=42)

    result = await middleware(handler, event, data)

    handler.assert_awaited_once_with(event, data)
    assert result == "ok"


@pytest.mark.asyncio
async def test_drops_unauthorized_user() -> None:
    """Return None without calling handler when sender is not whitelisted."""
    middleware = make_middleware(allowed=[42])
    handler = AsyncMock()
    event = MagicMock()
    data = make_update_data(user_id=99)

    result = await middleware(handler, event, data)

    handler.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_drops_anonymous_update() -> None:
    """Return None without calling handler for anonymous updates (no user)."""
    middleware = make_middleware(allowed=[42])
    handler = AsyncMock()
    event = MagicMock()
    data = make_update_data(user_id=None)

    result = await middleware(handler, event, data)

    handler.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_multiple_allowed_ids() -> None:
    """Allow any user whose ID is in the whitelist."""
    middleware = make_middleware(allowed=[1, 2, 3])
    handler = AsyncMock(return_value="yes")
    event = MagicMock()

    for uid in [1, 2, 3]:
        handler.reset_mock()
        data = make_update_data(user_id=uid)
        result = await middleware(handler, event, data)
        assert result == "yes"
        handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_whitelist_drops_all() -> None:
    """Drop every update when the whitelist is empty."""
    middleware = make_middleware(allowed=[])
    handler = AsyncMock()
    event = MagicMock()
    data = make_update_data(user_id=42)

    result = await middleware(handler, event, data)

    handler.assert_not_awaited()
    assert result is None
