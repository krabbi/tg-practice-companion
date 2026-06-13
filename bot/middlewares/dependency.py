"""DependencyMiddleware — per-request session and service injection."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Config
from bot.repositories.practice_repository import PracticeRepository
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.repositories.user_repository import UserRepository
from bot.services.delivery_service import DeliveryService
from bot.services.practice_service import PracticeService
from bot.services.skip_day_service import SkipDayService
from bot.services.timezone_service import TimezoneService


class DependencyMiddleware(BaseMiddleware):
    """Build and inject all services and repositories per-request.

    Opens a single AsyncSession for the lifetime of each update,
    builds all repo/service objects, injects them into data{}, then
    closes the session after the handler returns.
    """

    def __init__(self, session_factory: async_sessionmaker, config: Config) -> None:  # type: ignore[type-arg]
        self._factory = session_factory
        self._config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Inject session and services, then call the handler."""
        async with self._factory() as session:
            # Repositories
            user_repo = UserRepository(session)
            practice_repo = PracticeRepository(session)
            send_repo = PracticeSendRepository(session)

            # Services
            data["skip_day_service"] = SkipDayService(session, user_repo)
            data["timezone_service"] = TimezoneService(session, user_repo)
            data["practice_service"] = PracticeService(practice_repo)
            data["delivery_service"] = DeliveryService(data.get("bot") or data.get("event_bot"))

            # Expose repos for handlers that need raw DB access (rare)
            data["user_repo"] = user_repo
            data["practice_repo"] = practice_repo
            data["send_repo"] = send_repo

            return await handler(event, data)
