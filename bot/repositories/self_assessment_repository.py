"""Repository for SelfAssessment records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, SelfAssessment


class SelfAssessmentRepository:
    """CRUD access for SelfAssessment records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        journal_entry_id: uuid.UUID,
        leads_to_goals: bool,
        set_via: str,
    ) -> SelfAssessment:
        """Create and flush a new self-assessment; caller is responsible for commit."""
        assessment = SelfAssessment(
            journal_entry_id=journal_entry_id,
            leads_to_goals=leads_to_goals,
            set_via=set_via,
        )
        self._session.add(assessment)
        await self._session.flush()
        await self._session.refresh(assessment)
        return assessment

    async def get_by_entry_id(
        self, journal_entry_id: uuid.UUID, user_id: int
    ) -> SelfAssessment | None:
        """Return the SelfAssessment for the given journal entry owned by user_id, or None."""
        result = await self._session.execute(
            select(SelfAssessment)
            .join(JournalEntry, JournalEntry.id == SelfAssessment.journal_entry_id)
            .where(
                SelfAssessment.journal_entry_id == journal_entry_id,
                JournalEntry.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
