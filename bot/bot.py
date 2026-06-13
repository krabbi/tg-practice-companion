"""Factory functions for the aiogram Bot and Dispatcher."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import Config
from bot.handlers.commands import create_router
from bot.middlewares.auth import AuthMiddleware


def create_bot(config: Config) -> Bot:
    """Instantiate the aiogram Bot with HTML parse mode as default."""
    return Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(config: Config) -> Dispatcher:
    """Build and wire the Dispatcher: middlewares + routers in canonical order.

    Router registration order is load-bearing: the commands router is first so
    that /start and /help are matched before the catch-all journal router (M2).
    """
    dp = Dispatcher()

    # Auth middleware runs on every incoming update before any handler sees it
    dp.update.outer_middleware(AuthMiddleware(config.allowed_user_ids))

    # Register routers in canonical order (order matters for M2 catch-all)
    dp.include_router(create_router())

    return dp
