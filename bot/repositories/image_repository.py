"""Repository for MotivationalImage records."""

import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    async def get_active(self, user_id: int) -> list[MotivationalImage]:
        """Return all active motivational images for user_id."""
        result = await self._session.execute(
            select(MotivationalImage).where(
                MotivationalImage.active.is_(True), MotivationalImage.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def random_active(self, user_id: int) -> MotivationalImage | None:
        """Return a uniformly random active motivational image for user_id with its media_asset, or None."""
        result = await self._session.execute(
            select(MotivationalImage)
            .where(MotivationalImage.active.is_(True), MotivationalImage.user_id == user_id)
            .options(selectinload(MotivationalImage.media_asset))
        )
        images = list(result.scalars().all())
        return random.choice(images) if images else None

    async def get_by_media_asset_id(
        self, media_asset_id: uuid.UUID, user_id: int
    ) -> MotivationalImage | None:
        """Return the MotivationalImage with the given media_asset_id for user_id, or None."""
        result = await self._session.execute(
            select(MotivationalImage).where(
                MotivationalImage.media_asset_id == media_asset_id,
                MotivationalImage.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
