"""Admin service for CRUD operations on WantListItem rows (Stage 2 web API)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.lists import WantListItem
from bot.repositories.want_list_repository import WantListRepository


class WantAdminService:
    """Create, read, update, and delete want-list items; owns transaction commit."""

    def __init__(self, session: AsyncSession, repo: WantListRepository) -> None:
        self._session = session
        self._repo = repo

    async def list_for_user(self, user_id: int) -> list[WantListItem]:
        """Return all want-list items for the given user, oldest first."""
        return await self._repo.list_for_user(user_id)

    async def create(self, *, user_id: int, text: str) -> WantListItem:
        """Create a new want-list item and commit."""
        item = await self._repo.create(user_id=user_id, text=text)
        await self._session.commit()
        return item

    async def update(
        self,
        item_id: uuid.UUID,
        user_id: int,
        *,
        text: str | None = None,
        done: bool | None = None,
    ) -> WantListItem | None:
        """Update text and/or done for user_id; commit and return item, or None if not found/not owned."""
        item = await self._repo.update(item_id, user_id, text=text, done=done)
        if item is None:
            return None
        await self._session.commit()
        return item

    async def delete(self, item_id: uuid.UUID, user_id: int) -> bool:
        """Delete item for user_id; commit and return True, or False if not found/not owned."""
        found = await self._repo.delete(item_id, user_id)
        if found:
            await self._session.commit()
        return found
