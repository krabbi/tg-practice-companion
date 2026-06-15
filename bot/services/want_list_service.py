"""Service for the want-list feature (AC-9)."""

import random

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.lists import WantListItem
from bot.repositories.want_list_repository import WantListRepository


class WantListService:
    """Business logic for /want and /wants commands and the 12:00 random pick."""

    def __init__(self, session: AsyncSession, want_list_repo: WantListRepository) -> None:
        self._session = session
        self._repo = want_list_repo

    async def add(self, user_id: int, text: str) -> WantListItem:
        """Insert a new want-list item for the user and commit."""
        item = await self._repo.create(user_id=user_id, text=text)
        await self._session.commit()
        return item

    async def list_active(self, user_id: int) -> list[WantListItem]:
        """Return all undone want-list items for the user, oldest first."""
        all_items = await self._repo.list_for_user(user_id)
        return [item for item in all_items if not item.done]

    async def random_active(self, user_id: int) -> WantListItem | None:
        """Return a uniformly random undone item, or None if none exist."""
        active = await self.list_active(user_id)
        if not active:
            return None
        return random.choice(active)
