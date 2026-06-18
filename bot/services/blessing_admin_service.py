"""Admin service for CRUD operations on MorningBlessing rows (Stage 2 web API)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MorningBlessing
from bot.repositories.blessing_repository import BlessingRepository


class BlessingAdminService:
    """Create, read, update, delete, and reorder morning blessings; owns transaction commit."""

    def __init__(self, session: AsyncSession, repo: BlessingRepository) -> None:
        self._session = session
        self._repo = repo

    async def list_all(self) -> list[MorningBlessing]:
        """Return all blessings ordered by rotation_order."""
        return await self._repo.list_all()

    async def create(self, *, user_id: int, text: str, active: bool = True) -> MorningBlessing:
        """Create a new blessing appended to the end of the rotation order and commit."""
        existing = await self._repo.list_all()
        next_order = (max((b.rotation_order for b in existing), default=0)) + 1
        blessing = await self._repo.create(
            user_id=user_id, text=text, rotation_order=next_order, active=active
        )
        await self._session.commit()
        return blessing

    async def update(
        self,
        blessing_id: uuid.UUID,
        *,
        text: str | None = None,
        active: bool | None = None,
    ) -> MorningBlessing | None:
        """Update text and/or active; commit and return row, or None if not found."""
        blessing = await self._repo.update(blessing_id, text=text, active=active)
        if blessing is None:
            return None
        await self._session.commit()
        return blessing

    async def delete(self, blessing_id: uuid.UUID) -> bool:
        """Delete blessing by id; commit and return True, or False if not found."""
        found = await self._repo.delete(blessing_id)
        if found:
            await self._session.commit()
        return found

    async def reorder(self, blessing_ids: list[uuid.UUID]) -> list[MorningBlessing]:
        """Reassign rotation_order 1..N to the given IDs in the supplied order and commit.

        All existing blessing IDs must be included; raises ValueError if any are missing
        or if the list includes unknown IDs.
        """
        existing = await self._repo.list_all()
        existing_ids = {b.id for b in existing}
        input_ids = set(blessing_ids)

        unknown = input_ids - existing_ids
        if unknown:
            raise ValueError(f"Unknown blessing IDs: {unknown!r}")

        missing = existing_ids - input_ids
        if missing:
            raise ValueError(f"Missing blessing IDs (all must be included): {missing!r}")

        blessings = await self._repo.reorder(blessing_ids)
        await self._session.commit()
        return blessings
