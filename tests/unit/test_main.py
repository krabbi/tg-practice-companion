"""Tests for bot/bot.py — dispatcher builds and routers are registered."""

import pytest

from bot.bot import create_dispatcher
from bot.config import Config


def make_config(**overrides: object) -> Config:
    """Construct a minimal valid Config."""
    base = {
        "telegram_bot_token": "9999999999:AAFakeTokenForTestingPurposesOnly",
        "anthropic_api_key": "sk-ant-fake",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "allowed_user_ids": "123456789",
    }
    base.update(overrides)
    return Config.model_validate(base)


@pytest.fixture(scope="module")
def dispatcher():  # type: ignore[return]
    """Return a single Dispatcher instance shared across all tests in this module.

    Sharing avoids the aiogram 'Router is already attached' error that would
    occur if create_dispatcher (which calls create_router()) were invoked
    multiple times with the same router singleton.
    """
    return create_dispatcher(make_config())


def test_create_dispatcher_returns_dispatcher(dispatcher) -> None:  # type: ignore[no-untyped-def]
    """create_dispatcher returns an aiogram Dispatcher instance."""
    from aiogram import Dispatcher

    assert isinstance(dispatcher, Dispatcher)


def test_commands_router_is_registered(dispatcher) -> None:  # type: ignore[no-untyped-def]
    """The 'commands' router is included in the dispatcher."""
    registered_names = [r.name for r in dispatcher.sub_routers]
    assert "commands" in registered_names


def test_auth_middleware_is_wired(dispatcher) -> None:  # type: ignore[no-untyped-def]
    """AuthMiddleware is registered as an outer middleware on the dispatcher."""
    from bot.middlewares.auth import AuthMiddleware

    middleware_types = [type(m) for m in dispatcher.update.outer_middleware._middlewares]
    assert AuthMiddleware in middleware_types
