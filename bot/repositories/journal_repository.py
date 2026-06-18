"""Repository for JournalEntry records."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, SelfAssessment
from bot.models.practice import Practice


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


@dataclass(frozen=True)
class JournalEntryRow:
    """Flat projection of a journal entry with joined practice name and self-assessment."""

    id: uuid.UUID
    text: str
    source: str
    created_at: datetime
    practice_id: uuid.UUID | None
    practice_name: str | None
    leads_to_goals: bool | None
    assessment_set_via: str | None


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

    async def get_by_id(self, entry_id: uuid.UUID, user_id: int) -> JournalEntry | None:
        """Return the JournalEntry with the given id owned by user_id, or None."""
        result = await self._session.execute(
            select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_details(
        self, entry_id: uuid.UUID, user_id: int
    ) -> JournalEntryRow | None:
        """Return a JournalEntryRow with joined practice name and self-assessment for user_id, or None."""
        result = await self._session.execute(
            select(
                JournalEntry.id,
                JournalEntry.text,
                JournalEntry.source,
                JournalEntry.created_at,
                JournalEntry.practice_id,
                Practice.name.label("practice_name"),
                SelfAssessment.leads_to_goals,
                SelfAssessment.set_via.label("assessment_set_via"),
            )
            .outerjoin(Practice, Practice.id == JournalEntry.practice_id)
            .outerjoin(SelfAssessment, SelfAssessment.journal_entry_id == JournalEntry.id)
            .where(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return JournalEntryRow(
            id=row.id,
            text=row.text,
            source=row.source,
            created_at=row.created_at,
            practice_id=row.practice_id,
            practice_name=row.practice_name,
            leads_to_goals=row.leads_to_goals,
            assessment_set_via=row.assessment_set_via,
        )

    async def list_paginated(
        self,
        user_id: int,
        *,
        page: int,
        page_size: int,
        date_from: date | None = None,
        date_to: date | None = None,
        practice_id: uuid.UUID | None = None,
    ) -> tuple[list[JournalEntryRow], int]:
        """Return a page of journal entries with joined practice name and self-assessment.

        Filters (all optional): date_from/date_to (inclusive), practice_id.
        Returns (rows, total_count).
        """
        conditions = [JournalEntry.user_id == user_id]
        if date_from is not None:
            conditions.append(func.date(JournalEntry.created_at) >= date_from)
        if date_to is not None:
            conditions.append(func.date(JournalEntry.created_at) <= date_to)
        if practice_id is not None:
            conditions.append(JournalEntry.practice_id == practice_id)

        count_result = await self._session.execute(
            select(func.count(JournalEntry.id)).where(*conditions)
        )
        total: int = count_result.scalar_one() or 0

        rows_result = await self._session.execute(
            select(
                JournalEntry.id,
                JournalEntry.text,
                JournalEntry.source,
                JournalEntry.created_at,
                JournalEntry.practice_id,
                Practice.name.label("practice_name"),
                SelfAssessment.leads_to_goals,
                SelfAssessment.set_via.label("assessment_set_via"),
            )
            .outerjoin(Practice, Practice.id == JournalEntry.practice_id)
            .outerjoin(SelfAssessment, SelfAssessment.journal_entry_id == JournalEntry.id)
            .where(*conditions)
            .order_by(JournalEntry.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = [
            JournalEntryRow(
                id=r.id,
                text=r.text,
                source=r.source,
                created_at=r.created_at,
                practice_id=r.practice_id,
                practice_name=r.practice_name,
                leads_to_goals=r.leads_to_goals,
                assessment_set_via=r.assessment_set_via,
            )
            for r in rows_result.all()
        ]
        return items, total

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
