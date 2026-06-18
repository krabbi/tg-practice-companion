"""DependencyMiddleware — per-request session and service injection."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Config
from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.practice_repository import PracticeRepository
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.repositories.self_assessment_repository import SelfAssessmentRepository
from bot.repositories.user_repository import UserRepository
from bot.repositories.want_list_repository import WantListRepository
from bot.services.assessment_service import AssessmentService
from bot.services.delivery_service import DeliveryService
from bot.services.good_deed_service import GoodDeedService
from bot.services.journal_service import JournalService
from bot.services.practice_service import PracticeService
from bot.services.report_service import ReportService
from bot.services.skip_day_service import SkipDayService
from bot.services.timezone_service import TimezoneService
from bot.services.transcription_service import TranscriptionService
from bot.services.user_service import UserService
from bot.services.want_list_service import WantListService


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
            journal_repo = JournalRepository(session)
            prompt_repo = PendingPromptRepository(session)
            assessment_repo = SelfAssessmentRepository(session)
            want_list_repo = WantListRepository(session)
            good_deed_repo = GoodDeedRepository(session)

            # Provision the User row on first contact
            event_from_user = data.get("event_from_user")
            if event_from_user is not None:
                user_service = UserService(session, user_repo)
                await user_service.get_or_create(
                    event_from_user.id, language=self._config.default_language
                )

            # Services
            data["skip_day_service"] = SkipDayService(session, user_repo)
            data["timezone_service"] = TimezoneService(session, user_repo)
            data["practice_service"] = PracticeService(practice_repo)
            data["delivery_service"] = DeliveryService(data.get("bot") or data.get("event_bot"))
            data["journal_service"] = JournalService(session, journal_repo, prompt_repo)
            data["assessment_service"] = AssessmentService(
                session, assessment_repo, journal_repo, prompt_repo
            )
            data["want_list_service"] = WantListService(session, want_list_repo)
            data["good_deed_service"] = GoodDeedService(
                session, good_deed_repo, user_repo, prompt_repo
            )
            data["report_service"] = ReportService(journal_repo, good_deed_repo, send_repo)

            # Expose repos needed by handler filters
            data["prompt_repo"] = prompt_repo

            # Optional — injected as None when Groq credentials are missing
            if self._config.groq_api_key:
                data["transcription_service"] = TranscriptionService(self._config)
            else:
                data["transcription_service"] = None

            # Expose repos for handlers that need raw DB access (rare)
            data["user_repo"] = user_repo
            data["practice_repo"] = practice_repo
            data["send_repo"] = send_repo

            return await handler(event, data)
