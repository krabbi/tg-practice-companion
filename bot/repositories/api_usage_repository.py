"""Repository for ApiUsageLog records."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import ApiUsageLog


class ApiUsageRepository:
    """CRUD access for ApiUsageLog records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, log: ApiUsageLog) -> ApiUsageLog:
        """Flush and refresh a usage log row; caller is responsible for commit."""
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def get_by_id(self, log_id: uuid.UUID) -> ApiUsageLog | None:
        """Return the ApiUsageLog with the given id, or None."""
        result = await self._session.execute(
            select(ApiUsageLog).where(ApiUsageLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def sum_cost_since(self, since: datetime) -> Decimal:
        """Return the total cost_usd for all log rows at or after `since`."""
        result = await self._session.execute(
            select(func.sum(ApiUsageLog.cost_usd)).where(ApiUsageLog.created_at >= since)
        )
        total = result.scalar_one_or_none()
        return Decimal(str(total)) if total is not None else Decimal("0")
