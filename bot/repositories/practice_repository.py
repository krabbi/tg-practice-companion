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

    async def get_active_practices(self, user_id: int) -> list[Practice]:
        """Return all active Practice rows for user_id, eagerly loading their media_asset."""
        result = await self._session.execute(
            select(Practice)
            .where(Practice.active.is_(True), Practice.user_id == user_id)
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

    async def get_by_name(self, name: str, user_id: int) -> Practice | None:
        """Return a Practice by name for the given user (used for idempotent seeding), or None."""
        result = await self._session.execute(
            select(Practice).where(Practice.name == name, Practice.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def save(self, practice: Practice) -> Practice:
        """Flush and refresh the practice row; caller is responsible for commit."""
        self._session.add(practice)
        await self._session.flush()
        await self._session.refresh(practice)
        return practice

    async def get_media_asset_by_id(self, asset_id: uuid.UUID, user_id: int) -> MediaAsset | None:
        """Return a MediaAsset by its UUID for the given user, or None."""
        result = await self._session.execute(
            select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def save_media_asset(self, asset: MediaAsset) -> MediaAsset:
        """Flush and refresh the media asset row; caller is responsible for commit."""
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def list_all(self, user_id: int, active: bool | None = None) -> list[Practice]:
        """Return all Practice rows for user_id (optionally filtered by active flag), ordered by sort_order."""
        query = (
            select(Practice)
            .where(Practice.user_id == user_id)
            .options(selectinload(Practice.media_asset))
            .order_by(Practice.sort_order)
        )
        if active is not None:
            query = query.where(Practice.active.is_(active))
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def delete(self, practice_id: uuid.UUID, user_id: int) -> bool:
        """Delete a Practice by UUID for the given user; flush. Returns False when not found or not owned."""
        practice = await self.get_by_id(practice_id)
        if practice is None or practice.user_id != user_id:
            return False
        await self._session.delete(practice)
        await self._session.flush()
        return True

    async def get_media_asset_by_telegram_file_id(self, telegram_file_id: str) -> MediaAsset | None:
        """Return the MediaAsset with the given telegram_file_id, or None."""
        result = await self._session.execute(
            select(MediaAsset).where(MediaAsset.telegram_file_id == telegram_file_id)
        )
        return result.scalar_one_or_none()
