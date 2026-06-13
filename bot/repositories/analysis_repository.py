"""Repository for DailyAiAnalysis records."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import DailyAiAnalysis


class AnalysisRepository:
    """CRUD access for DailyAiAnalysis records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, analysis: DailyAiAnalysis) -> DailyAiAnalysis:
        """Flush and refresh an analysis row; caller is responsible for commit."""
        self._session.add(analysis)
        await self._session.flush()
        await self._session.refresh(analysis)
        return analysis

    async def get_by_id(self, analysis_id: uuid.UUID) -> DailyAiAnalysis | None:
        """Return the DailyAiAnalysis with the given id, or None."""
        result = await self._session.execute(
            select(DailyAiAnalysis).where(DailyAiAnalysis.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_date(
        self, user_id: int, analysis_date: date
    ) -> DailyAiAnalysis | None:
        """Return the analysis for a specific user and date, or None."""
        result = await self._session.execute(
            select(DailyAiAnalysis).where(
                DailyAiAnalysis.user_id == user_id,
                DailyAiAnalysis.analysis_date == analysis_date,
            )
        )
        return result.scalar_one_or_none()
