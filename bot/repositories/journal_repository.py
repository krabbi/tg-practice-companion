"""Repository for JournalEntry records."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, SelfAssessment


@dataclass(frozen=True)
class PeriodStats:
    """Aggregated counts for a date range of journal entries."""

    n_total: int
    n_leads: int


@dataclass(frozen=True)
class DailyStats:
    """Count of yesterday's journal entries and those marked as leading to goals."""

    n_total: int
    n_leads: int


class JournalRepository:
    """CRUD access for JournalEntry records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        text: str,
        source: str,
        practice_id: uuid.UUID | None,
    ) -> JournalEntry:
        """Create and flush a new journal entry; caller is responsible for commit."""
        entry = JournalEntry(
            user_id=user_id,
            text=text,
            source=source,
            practice_id=practice_id,
        )
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def get_by_id(self, entry_id: uuid.UUID) -> JournalEntry | None:
        """Return the JournalEntry with the given id, or None."""
        result = await self._session.execute(
            select(JournalEntry).where(JournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def daily_stats(self, user_id: int, target_date: date) -> DailyStats:
        """Return n_total and n_leads for a user's journal entries on target_date.

        Counts all JournalEntry rows whose created_at falls on target_date (date
        comparison is done by casting to DATE in the DB).  n_leads counts how many
        of those entries have a SelfAssessment with leads_to_goals=True.
        """
        # Total entries on the target date (cast DateTime → Date for comparison)
        total_result = await self._session.execute(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.user_id == user_id,
                func.date(JournalEntry.created_at) == target_date,
            )
        )
        n_total: int = total_result.scalar_one() or 0

        # Entries that have a self-assessment marking them as leading to goals
        leads_result = await self._session.execute(
            select(func.count(JournalEntry.id))
            .join(SelfAssessment, SelfAssessment.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntry.user_id == user_id,
                func.date(JournalEntry.created_at) == target_date,
                SelfAssessment.leads_to_goals.is_(True),
            )
        )
        n_leads: int = leads_result.scalar_one() or 0

        return DailyStats(n_total=n_total, n_leads=n_leads)

    async def period_stats(self, user_id: int, start: date, end: date) -> PeriodStats:
        """Return n_total and n_leads for journal entries within [start, end] inclusive.

        Both start and end are inclusive date boundaries.
        """
        total_result = await self._session.execute(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.user_id == user_id,
                func.date(JournalEntry.created_at) >= start,
                func.date(JournalEntry.created_at) <= end,
            )
        )
        n_total: int = total_result.scalar_one() or 0

        leads_result = await self._session.execute(
            select(func.count(JournalEntry.id))
            .join(SelfAssessment, SelfAssessment.journal_entry_id == JournalEntry.id)
            .where(
                JournalEntry.user_id == user_id,
                func.date(JournalEntry.created_at) >= start,
                func.date(JournalEntry.created_at) <= end,
                SelfAssessment.leads_to_goals.is_(True),
            )
        )
        n_leads: int = leads_result.scalar_one() or 0

        return PeriodStats(n_total=n_total, n_leads=n_leads)
