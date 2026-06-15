"""Repository for GoodDeed records."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.lists import GoodDeed


class GoodDeedRepository:
    """CRUD access for GoodDeed records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, text: str, deed_date: date) -> GoodDeed:
        """Create and flush a new good deed; caller commits."""
        deed = GoodDeed(user_id=user_id, text=text, deed_date=deed_date)
        self._session.add(deed)
        await self._session.flush()
        await self._session.refresh(deed)
        return deed

    async def get_by_id(self, deed_id: uuid.UUID) -> GoodDeed | None:
        """Return the GoodDeed with the given id, or None."""
        result = await self._session.execute(select(GoodDeed).where(GoodDeed.id == deed_id))
        return result.scalar_one_or_none()

    async def list_by_date(self, user_id: int, deed_date: date) -> list[GoodDeed]:
        """Return all good deeds for the given user and date, oldest first."""
        result = await self._session.execute(
            select(GoodDeed)
            .where(GoodDeed.user_id == user_id, GoodDeed.deed_date == deed_date)
            .order_by(GoodDeed.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, deed_id: uuid.UUID) -> bool:
        """Delete the good deed by id; return True if deleted, False if not found."""
        deed = await self.get_by_id(deed_id)
        if deed is None:
            return False
        await self._session.delete(deed)
        await self._session.flush()
        return True
