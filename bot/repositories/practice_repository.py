"""Repository for Practice and MediaAsset records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models.practice import MediaAsset, Practice


class PracticeRepository:
    """CRUD access for Practice records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_practices(self) -> list[Practice]:
        """Return all active Practice rows, eagerly loading their media_asset."""
        result = await self._session.execute(
            select(Practice)
            .where(Practice.active.is_(True))
            .options(selectinload(Practice.media_asset))
            .order_by(Practice.sort_order)
        )
        return list(result.scalars().all())

    async def get_by_id(self, practice_id: uuid.UUID) -> Practice | None:
        """Return a Practice by its UUID, or None."""
        result = await self._session.execute(
            select(Practice)
            .where(Practice.id == practice_id)
            .options(selectinload(Practice.media_asset))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Practice | None:
        """Return a Practice by name (used for idempotent seeding), or None."""
        result = await self._session.execute(select(Practice).where(Practice.name == name))
        return result.scalar_one_or_none()

    async def save(self, practice: Practice) -> Practice:
        """Flush and refresh the practice row; caller is responsible for commit."""
        self._session.add(practice)
        await self._session.flush()
        await self._session.refresh(practice)
        return practice

    async def get_media_asset_by_id(self, asset_id: uuid.UUID) -> MediaAsset | None:
        """Return a MediaAsset by its UUID, or None."""
        result = await self._session.execute(select(MediaAsset).where(MediaAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def save_media_asset(self, asset: MediaAsset) -> MediaAsset:
        """Flush and refresh the media asset row; caller is responsible for commit."""
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset
