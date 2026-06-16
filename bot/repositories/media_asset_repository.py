"""Repository for MediaAsset records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import MediaAsset


class MediaAssetRepository:
    """CRUD access for MediaAsset records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, asset: MediaAsset) -> MediaAsset:
        """Flush and refresh a new MediaAsset row; caller is responsible for commit."""
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def list_all(self, kind: str | None = None) -> list[MediaAsset]:
        """Return all MediaAsset rows ordered by creation time, optionally filtered by kind."""
        query = select(MediaAsset).order_by(MediaAsset.created_at.desc())
        if kind is not None:
            query = query.where(MediaAsset.kind == kind)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get(self, asset_id: uuid.UUID) -> MediaAsset | None:
        """Return a MediaAsset by its UUID, or None."""
        result = await self._session.execute(select(MediaAsset).where(MediaAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def delete(self, asset_id: uuid.UUID) -> bool:
        """Delete a MediaAsset by UUID and flush. Returns False when not found."""
        asset = await self.get(asset_id)
        if asset is None:
            return False
        await self._session.delete(asset)
        await self._session.flush()
        return True
