"""Admin service for media asset upload and motivational-image pool management (B4)."""

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MotivationalImage
from bot.models.practice import MediaAsset
from bot.repositories.image_repository import ImageRepository
from bot.repositories.media_asset_repository import MediaAssetRepository
from bot.services.storage_service import S3StorageService

_log = logging.getLogger(__name__)

# Telegram Bot API upload cap for send_video; larger files must stay S3-only.
_TELEGRAM_VIDEO_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB


class MediaAssetError(Exception):
    """Raised when media asset data fails validation."""


class MediaAdminService:
    """Upload media files to S3 + Telegram, manage the motivational-image pool."""

    def __init__(
        self,
        session: AsyncSession,
        repo: MediaAssetRepository,
        image_repo: ImageRepository,
        bot: object | None,
        chat_id: int | None,
        storage: S3StorageService,
    ) -> None:
        self._session = session
        self._repo = repo
        self._image_repo = image_repo
        self._bot = bot
        self._chat_id = chat_id
        self._storage = storage

    async def upload(
        self,
        data: bytes,
        filename: str,
        kind: str,
        mime: str,
        user_id: int,
    ) -> MediaAsset:
        """Upload bytes to S3, capture Telegram file_id, and commit a MediaAsset row.

        Order of operations:
          1. PUT to S3 — abort entirely if this fails (no row, no orphan).
          2. Send to Telegram to capture file_id. If this raises, best-effort
             delete the S3 object then re-raise.
          3. Create DB row and commit.

        When bot is None (e.g. in tests), the Telegram upload step is skipped and
        telegram_file_id is left null. The storage_path invariant is always satisfied.
        """
        if kind not in ("audio", "image", "video"):
            raise MediaAssetError(f"Invalid kind: {kind!r}; must be 'audio', 'image', or 'video'")

        asset_id = uuid.uuid4()
        suffix = Path(filename).suffix or _kind_default_suffix(kind)
        key = f"{kind}/{asset_id}{suffix}"

        await self._storage.put_object(key, data, content_type=mime)

        telegram_file_id: str | None = None
        if self._bot is not None and self._chat_id is not None:
            try:
                telegram_file_id = await _send_to_telegram(
                    self._bot, self._chat_id, data, filename, kind
                )
            except Exception:
                try:
                    await self._storage.delete_object(key)
                except Exception:
                    _log.warning("Failed to clean up orphan S3 object %r after Telegram error", key)
                raise

        asset = MediaAsset(
            id=asset_id,
            user_id=user_id,
            kind=kind,
            storage_path=key,
            telegram_file_id=telegram_file_id,
            mime=mime,
            original_filename=filename,
        )
        await self._repo.create(asset)
        await self._session.commit()
        return asset

    async def list_assets(self, user_id: int, kind: str | None = None) -> list[MediaAsset]:
        """Return all media assets for user_id, optionally filtered by kind."""
        return await self._repo.list_all(user_id, kind)

    async def get_asset(self, asset_id: uuid.UUID, user_id: int) -> MediaAsset | None:
        """Return a single media asset by UUID for user_id, or None."""
        return await self._repo.get(asset_id, user_id)

    def generate_presigned_url(self, storage_path: str, expires_in: int) -> str:
        """Return a presigned S3 GET URL for *storage_path*."""
        return self._storage.generate_presigned_url(storage_path, expires_in)

    async def delete_asset(self, asset_id: uuid.UUID, user_id: int) -> bool:
        """Delete a MediaAsset row for user_id and its S3 object (best-effort). Returns False when not found or not owned."""
        asset = await self._repo.get(asset_id, user_id)
        if asset is None:
            return False
        storage_path = asset.storage_path
        await self._repo.delete(asset_id, user_id)
        await self._session.commit()
        if storage_path is not None:
            try:
                await self._storage.delete_object(storage_path)
            except Exception:
                _log.warning("Failed to delete S3 object %r; row already removed", storage_path)
        return True

    async def create_motivational_image(
        self,
        media_asset_id: uuid.UUID,
        user_id: int,
        active: bool = True,
    ) -> MotivationalImage:
        """Add a MediaAsset to the motivational-image pool and commit."""
        asset = await self._repo.get(media_asset_id, user_id)
        if asset is None:
            raise MediaAssetError(f"MediaAsset {media_asset_id} not found")
        if asset.kind != "image":
            raise MediaAssetError(
                f"MediaAsset {media_asset_id} has kind={asset.kind!r}; must be 'image'"
            )
        image = MotivationalImage(
            id=uuid.uuid4(), user_id=user_id, media_asset_id=media_asset_id, active=active
        )
        await self._image_repo.save(image)
        await self._session.commit()
        return image


def _kind_default_suffix(kind: str) -> str:
    """Return the default file extension for a given media kind."""
    if kind == "image":
        return ".jpg"
    if kind == "video":
        return ".mp4"
    return ".mp3"


async def _send_to_telegram(
    bot: object,
    chat_id: int,
    data: bytes,
    filename: str,
    kind: str,
) -> str | None:
    """Send bytes to Telegram and return the telegram_file_id, or None if no file_id returned."""
    from aiogram.types import BufferedInputFile

    input_file = BufferedInputFile(data, filename=filename)
    if kind == "image":
        msg = await bot.send_photo(chat_id=chat_id, photo=input_file)  # type: ignore[union-attr]
        if msg.photo:
            return msg.photo[-1].file_id
    elif kind == "video":
        if len(data) > _TELEGRAM_VIDEO_SIZE_LIMIT:
            _log.warning(
                "video upload skipped for Telegram (%d bytes > %d byte limit) — "
                "S3-only; scheduled delivery will log an error for this asset",
                len(data),
                _TELEGRAM_VIDEO_SIZE_LIMIT,
            )
            return None
        msg = await bot.send_video(chat_id=chat_id, video=input_file)  # type: ignore[union-attr]
        if msg.video:
            return msg.video.file_id
    else:
        msg = await bot.send_audio(chat_id=chat_id, audio=input_file)  # type: ignore[union-attr]
        if msg.audio:
            return msg.audio.file_id
    return None
