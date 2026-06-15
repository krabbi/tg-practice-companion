"""Service for the good-deeds feature (AC-10)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.lists import GoodDeed
from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.user_repository import UserRepository

_PROMPT_EXPIRY_HOURS = 24


class GoodDeedService:
    """Business logic for recording a user's good deed of the day (AC-10).

    store_today() looks up the user's timezone so deed_date reflects
    local calendar date rather than UTC.  It also consumes the pending
    good_deeds prompt atomically in the same commit.
    """

    def __init__(
        self,
        session: AsyncSession,
        good_deed_repo: GoodDeedRepository,
        user_repo: UserRepository,
        prompt_repo: PendingPromptRepository,
    ) -> None:
        self._session = session
        self._repo = good_deed_repo
        self._user_repo = user_repo
        self._prompt_repo = prompt_repo

    async def store_today(self, user_id: int, text: str) -> GoodDeed:
        """Insert one free-text GoodDeed row for local today and commit.

        Also consumes the newest unconsumed good_deeds pending_prompt so
        subsequent messages are not mistakenly captured as deeds.
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        tz_name = (user.timezone if user is not None else None) or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            tz = ZoneInfo("UTC")

        deed_date = datetime.now(UTC).astimezone(tz).date()
        deed = await self._repo.create(user_id=user_id, text=text, deed_date=deed_date)

        not_before = datetime.now(UTC) - timedelta(hours=_PROMPT_EXPIRY_HOURS)
        prompt = await self._prompt_repo.newest_unconsumed(user_id, not_before=not_before)
        if prompt is not None and prompt.kind == "good_deeds":
            await self._prompt_repo.mark_consumed(prompt.id)

        await self._session.commit()
        return deed
