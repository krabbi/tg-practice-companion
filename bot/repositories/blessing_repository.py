"""Repository for MorningBlessing records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MorningBlessing


class BlessingRepository:
    """CRUD access for MorningBlessing records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, blessing: MorningBlessing) -> MorningBlessing:
        """Flush and refresh a blessing row; caller is responsible for commit."""
        self._session.add(blessing)
        await self._session.flush()
        await self._session.refresh(blessing)
        return blessing

    async def get_by_id(self, blessing_id: uuid.UUID) -> MorningBlessing | None:
        """Return the MorningBlessing with the given id, or None."""
        result = await self._session.execute(
            select(MorningBlessing).where(MorningBlessing.id == blessing_id)
        )
        return result.scalar_one_or_none()

    async def get_active_ordered(self) -> list[MorningBlessing]:
        """Return all active blessings ordered by rotation_order ascending."""
        result = await self._session.execute(
            select(MorningBlessing)
            .where(MorningBlessing.active.is_(True))
            .order_by(MorningBlessing.rotation_order)
        )
        return list(result.scalars().all())
