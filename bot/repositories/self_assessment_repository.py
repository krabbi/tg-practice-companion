"""Repository for SelfAssessment records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import SelfAssessment


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

    async def get_by_entry_id(self, journal_entry_id: uuid.UUID) -> SelfAssessment | None:
        """Return the SelfAssessment for the given journal entry, or None."""
        result = await self._session.execute(
            select(SelfAssessment).where(SelfAssessment.journal_entry_id == journal_entry_id)
        )
        return result.scalar_one_or_none()
