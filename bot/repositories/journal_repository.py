"""Repository for JournalEntry records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry


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
