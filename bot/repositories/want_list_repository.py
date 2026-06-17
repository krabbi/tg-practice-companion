"""Repository for WantListItem records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.lists import WantListItem


class WantListRepository:
    """CRUD access for WantListItem records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, text: str) -> WantListItem:
        """Create and flush a new want-list item; caller commits."""
        item = WantListItem(user_id=user_id, text=text)
        self._session.add(item)
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> WantListItem | None:
        """Return the WantListItem with the given id, or None."""
        result = await self._session.execute(select(WantListItem).where(WantListItem.id == item_id))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[WantListItem]:
        """Return all want-list items for the given user, oldest first."""
        result = await self._session.execute(
            select(WantListItem)
            .where(WantListItem.user_id == user_id)
            .order_by(WantListItem.created_at)
        )
        return list(result.scalars().all())

    async def mark_done(self, item_id: uuid.UUID) -> WantListItem | None:
        """Set done=True on the item; return updated item or None if not found."""
        item = await self.get_by_id(item_id)
        if item is None:
            return None
        item.done = True
        await self._session.flush()
        return item

    async def update(
        self, item_id: uuid.UUID, *, text: str | None = None, done: bool | None = None
    ) -> WantListItem | None:
        """Update text and/or done on an item; return updated item or None if not found."""
        item = await self.get_by_id(item_id)
        if item is None:
            return None
        if text is not None:
            item.text = text
        if done is not None:
            item.done = done
        await self._session.flush()
        return item

    async def delete(self, item_id: uuid.UUID) -> bool:
        """Delete the item by id; return True if deleted, False if not found."""
        item = await self.get_by_id(item_id)
        if item is None:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True
