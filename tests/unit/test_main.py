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


def test_router_registration_order(dispatcher) -> None:  # type: ignore[no-untyped-def]
    """Routers are registered in the canonical load-bearing order (issue #4).

    Canonical order:
      1. commands      — /start, /help must match before catch-all
      2. (timezone_setup FSM slot reserved for M5 — not yet wired)
      3. assessment    — callback + command router
      4. skip_day      — command/callback router
      5. journal       — F.text/F.voice catch-all, StateFilter(None), MUST be last
    """
    registered_names = [r.name for r in dispatcher.sub_routers]

    # All four currently-wired routers must be present
    for name in ("commands", "assessment", "skip_day", "journal"):
        assert name in registered_names, f"Router '{name}' missing from dispatcher"

    # Verify strict index order
    idx_commands = registered_names.index("commands")
    idx_assessment = registered_names.index("assessment")
    idx_skip_day = registered_names.index("skip_day")
    idx_journal = registered_names.index("journal")

    assert idx_commands < idx_assessment, "commands must come before assessment"
    assert idx_assessment < idx_skip_day, "assessment must come before skip_day"
    assert idx_skip_day < idx_journal, "skip_day must come before journal"

    # journal must be strictly last among all registered routers
    assert idx_journal == len(registered_names) - 1, "journal router must be last"


def test_auth_middleware_is_wired(dispatcher) -> None:  # type: ignore[no-untyped-def]
    """AuthMiddleware is registered as an outer middleware on the dispatcher."""
    from bot.middlewares.auth import AuthMiddleware

    middleware_types = [type(m) for m in dispatcher.update.outer_middleware._middlewares]
    assert AuthMiddleware in middleware_types
