"""Admin service for CRUD operations on Practice rows (Stage 2 web API)."""

import re
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import Practice
from bot.repositories.practice_repository import PracticeRepository

HHMM_RE = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")


class PracticeValidationError(Exception):
    """Raised when practice data fails business-rule validation."""


class PracticeAdminService:
    """Create, update, and delete practices with schedule validation."""

    def __init__(
        self,
        session: AsyncSession,
        repo: PracticeRepository,
        send_window_start: int = 6,
        send_window_end: int = 22,
    ) -> None:
        self._session = session
        self._repo = repo
        self._window_start = send_window_start
        self._window_end = send_window_end

    def _check_anchor_window(self, name: str, interval_hours: int, anchor_hour: int) -> None:
        """Raise PracticeValidationError when no slot falls inside the send window."""
        if interval_hours < 1:
            raise PracticeValidationError("interval_hours must be >= 1")
        slots = {h for h in range(24) if (h - anchor_hour) % interval_hours == 0}
        admissible = [h for h in slots if self._window_start <= h < self._window_end]
        if not admissible:
            raise PracticeValidationError(
                f"Practice {name!r}: interval_hours={interval_hours} anchor_hour={anchor_hour} "
                f"yields no slot inside [{self._window_start:02d}:00, {self._window_end:02d}:00) "
                "— this practice would never fire"
            )

    def _validate_schedule(
        self,
        name: str,
        periodicity_type: str,
        interval_hours: int | None,
        schedule_times: list[str] | None,
        anchor_hour: int,
    ) -> None:
        """Validate schedule fields; raise PracticeValidationError on violations."""
        if periodicity_type == "every_n_hours":
            if interval_hours is None:
                raise PracticeValidationError(
                    "interval_hours is required when periodicity_type is every_n_hours"
                )
            self._check_anchor_window(name, interval_hours, anchor_hour)
        if periodicity_type == "fixed_times" and schedule_times:
            bad = [t for t in schedule_times if not HHMM_RE.match(t)]
            if bad:
                raise PracticeValidationError(f"Invalid HH:MM schedule_times entries: {bad!r}")

    async def list_all(self, active: bool | None = None) -> list[Practice]:
        """Return all practices, optionally filtered by active status."""
        return await self._repo.list_all(active)

    async def get(self, practice_id: uuid.UUID) -> Practice | None:
        """Return a practice by UUID, or None."""
        return await self._repo.get_by_id(practice_id)

    async def create(
        self,
        *,
        name: str,
        content_type: str,
        content: str | None,
        media_asset_id: uuid.UUID | None,
        periodicity_type: str,
        interval_hours: int | None,
        schedule_times: list[str] | None,
        anchor_hour: int,
        anchor_minute: int,
        active: bool,
        start_date: datetime | None,
        end_date: datetime | None,
        sort_order: int,
    ) -> Practice:
        """Create and commit a new Practice; raises PracticeValidationError on invalid data."""
        self._validate_schedule(name, periodicity_type, interval_hours, schedule_times, anchor_hour)
        practice = Practice(
            id=uuid.uuid4(),
            name=name,
            content_type=content_type,
            content=content,
            media_asset_id=media_asset_id,
            periodicity_type=periodicity_type,
            interval_hours=interval_hours,
            schedule_times=schedule_times,
            anchor_hour=anchor_hour,
            anchor_minute=anchor_minute,
            active=active,
            start_date=start_date,
            end_date=end_date,
            sort_order=sort_order,
        )
        await self._repo.save(practice)
        await self._session.commit()
        return practice

    async def update(self, practice_id: uuid.UUID, updates: dict) -> Practice | None:
        """Apply a partial update and commit; raises PracticeValidationError on violations."""
        practice = await self._repo.get_by_id(practice_id)
        if practice is None:
            return None
        for field, value in updates.items():
            setattr(practice, field, value)
        self._validate_schedule(
            practice.name,
            practice.periodicity_type,
            practice.interval_hours,
            practice.schedule_times,
            practice.anchor_hour or 0,
        )
        await self._repo.save(practice)
        await self._session.commit()
        return practice

    async def delete(self, practice_id: uuid.UUID) -> bool:
        """Delete a Practice by UUID and commit. Returns False when not found."""
        found = await self._repo.delete(practice_id)
        if found:
            await self._session.commit()
        return found
