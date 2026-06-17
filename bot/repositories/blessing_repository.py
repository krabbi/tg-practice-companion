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

    async def get_by_rotation_order(self, rotation_order: int) -> MorningBlessing | None:
        """Return the blessing with the given rotation_order, or None."""
        result = await self._session.execute(
            select(MorningBlessing).where(MorningBlessing.rotation_order == rotation_order)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[MorningBlessing]:
        """Return all blessings ordered by rotation_order ascending."""
        result = await self._session.execute(
            select(MorningBlessing).order_by(MorningBlessing.rotation_order)
        )
        return list(result.scalars().all())

    async def create(
        self, *, text: str, rotation_order: int, active: bool = True
    ) -> MorningBlessing:
        """Create and flush a new blessing; caller commits."""
        blessing = MorningBlessing(text=text, rotation_order=rotation_order, active=active)
        self._session.add(blessing)
        await self._session.flush()
        await self._session.refresh(blessing)
        return blessing

    async def update(
        self,
        blessing_id: uuid.UUID,
        *,
        text: str | None = None,
        active: bool | None = None,
    ) -> MorningBlessing | None:
        """Update text and/or active on a blessing; return updated row or None if not found."""
        blessing = await self.get_by_id(blessing_id)
        if blessing is None:
            return None
        if text is not None:
            blessing.text = text
        if active is not None:
            blessing.active = active
        await self._session.flush()
        return blessing

    async def delete(self, blessing_id: uuid.UUID) -> bool:
        """Delete a blessing by id; return True if deleted, False if not found."""
        blessing = await self.get_by_id(blessing_id)
        if blessing is None:
            return False
        await self._session.delete(blessing)
        await self._session.flush()
        return True

    async def reorder(self, blessing_ids: list[uuid.UUID]) -> list[MorningBlessing]:
        """Assign rotation_order 1..N to the given blessing IDs in the supplied order.

        Uses a two-pass approach to avoid violating the unique constraint during reassignment:
        first move all items to a large temporary offset, then assign final values.
        """
        blessings = []
        for bid in blessing_ids:
            b = await self.get_by_id(bid)
            if b is None:
                raise KeyError(str(bid))
            blessings.append(b)

        # Pass 1: assign unique values well above any realistic rotation_order.
        for i, b in enumerate(blessings):
            b.rotation_order = 1_000_000 + i
        await self._session.flush()

        # Pass 2: assign final 1-based values.
        for i, b in enumerate(blessings):
            b.rotation_order = i + 1
        await self._session.flush()
        return blessings
