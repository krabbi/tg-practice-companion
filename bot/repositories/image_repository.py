"""Repository for MotivationalImage records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MotivationalImage


class ImageRepository:
    """CRUD access for MotivationalImage records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, image: MotivationalImage) -> MotivationalImage:
        """Flush and refresh a motivational image row; caller is responsible for commit."""
        self._session.add(image)
        await self._session.flush()
        await self._session.refresh(image)
        return image

    async def get_by_id(self, image_id: uuid.UUID) -> MotivationalImage | None:
        """Return the MotivationalImage with the given id, or None."""
        result = await self._session.execute(
            select(MotivationalImage).where(MotivationalImage.id == image_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> list[MotivationalImage]:
        """Return all active motivational images."""
        result = await self._session.execute(
            select(MotivationalImage).where(MotivationalImage.active.is_(True))
        )
        return list(result.scalars().all())
