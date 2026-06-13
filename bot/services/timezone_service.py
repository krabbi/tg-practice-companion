"""Service for validating and persisting timezone changes."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from bot.exceptions import TimezoneError
from bot.models.user import User
from bot.repositories.user_repository import UserRepository


class TimezoneService:
    """Validates IANA timezone strings and persists them to the user row.

    Stamps users.tz_changed_at = now(UTC) on every successful change so that
    the backward-tz-jump guard in the scheduler tick can detect timezone shifts.
    """

    def __init__(self, session: AsyncSession, user_repo: UserRepository) -> None:
        self._session = session
        self._user_repo = user_repo

    async def set_timezone(self, telegram_id: int, tz_string: str) -> User:
        """Validate the IANA timezone string and persist it to the user row.

        Raises TimezoneError if the timezone string is not a valid IANA zone.
        Stamps tz_changed_at to UTC now on success.
        """
        # Validate the timezone string before touching the DB
        try:
            ZoneInfo(tz_string)
        except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
            raise TimezoneError(f"Invalid IANA timezone: {tz_string!r}") from exc

        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise TimezoneError(f"User {telegram_id} not found")

        user.timezone = tz_string
        user.tz_changed_at = datetime.now(UTC)
        await self._user_repo.save(user)
        await self._session.commit()
        return user
