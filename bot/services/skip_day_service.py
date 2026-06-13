"""Service for the skip-day feature (AC-5)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.user_repository import UserRepository


class SkipDayService:
    """Sets skip_until on the user row to silence practices for the rest of the day."""

    def __init__(self, session: AsyncSession, user_repo: UserRepository) -> None:
        self._session = session
        self._user_repo = user_repo

    async def skip_today(self, telegram_id: int) -> date:
        """Set skip_until = local today for the user, commit, and return the date.

        Uses the user's configured timezone to determine 'today'.
        Falls back to UTC if no timezone is set.
        """
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            # Defensive: should not happen given auth middleware, but handle gracefully
            return datetime.now(UTC).date()

        tz_string = user.timezone or "UTC"
        try:
            user_tz = ZoneInfo(tz_string)
        except (ZoneInfoNotFoundError, KeyError):
            user_tz = ZoneInfo("UTC")

        local_today = datetime.now(UTC).astimezone(user_tz).date()
        user.skip_until = local_today
        await self._user_repo.save(user)
        await self._session.commit()
        return local_today
