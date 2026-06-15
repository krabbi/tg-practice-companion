"""Factory functions for the aiogram Bot and Dispatcher."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Config
from bot.handlers import assessment, commands, journal, skip_day, want_list
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.dependency import DependencyMiddleware


def create_bot(config: Config) -> Bot:
    """Instantiate the aiogram Bot with HTML parse mode as default."""
    return Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    config: Config, session_factory: async_sessionmaker | None = None
) -> Dispatcher:  # type: ignore[type-arg]
    """Build and wire the Dispatcher: middlewares + routers in canonical order.

    Router registration order is load-bearing: the commands router is first so
    that /start and /help are matched before the catch-all journal router (M2).

    session_factory is optional so that tests that only exercise commands or auth
    can omit it; DependencyMiddleware is only wired when it is provided.
    """
    dp = Dispatcher()

    # Auth middleware runs on every incoming update before any handler sees it
    dp.update.outer_middleware(AuthMiddleware(config.allowed_user_ids))

    # DependencyMiddleware injects session + services when a factory is provided
    if session_factory is not None:
        dp.update.middleware(DependencyMiddleware(session_factory, config))

    # Register routers in canonical order (order is load-bearing — see issue #4).
    # 1. commands — /start, /help must match before the catch-all journal router
    dp.include_router(commands.create_router())
    # 2. timezone_setup FSM router slot (reserved for M5 — not yet wired)
    # 3. assessment callbacks + skip_day command/callback routers
    dp.include_router(assessment.create_router())
    dp.include_router(skip_day.create_router())
    dp.include_router(want_list.create_router())
    # 4. journal F.text / F.voice catch-all LAST (StateFilter(None) yields to FSM)
    dp.include_router(journal.create_router())

    return dp
