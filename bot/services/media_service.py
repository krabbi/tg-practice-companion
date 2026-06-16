"""Admin service for media asset upload and motivational-image pool management (B4)."""

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MotivationalImage
from bot.models.practice import MediaAsset
from bot.repositories.image_repository import ImageRepository
from bot.repositories.media_asset_repository import MediaAssetRepository


class MediaAssetError(Exception):
    """Raised when media asset data fails validation."""


class MediaAdminService:
    """Upload media files to disk + Telegram, manage the motivational-image pool."""

    def __init__(
        self,
        session: AsyncSession,
        repo: MediaAssetRepository,
        image_repo: ImageRepository,
        bot: object | None,
        chat_id: int | None,
        storage_dir: Path,
    ) -> None:
        self._session = session
        self._repo = repo
        self._image_repo = image_repo
        self._bot = bot
        self._chat_id = chat_id
        self._storage_dir = storage_dir

    async def upload(
        self,
        data: bytes,
        filename: str,
        kind: str,
        mime: str,
    ) -> MediaAsset:
        """Save bytes to disk, upload to Telegram to capture file_id, and commit a MediaAsset row.

        When bot is None (e.g. in tests), the Telegram upload step is skipped and
        telegram_file_id is left null. The storage_path invariant is always satisfied.
        """
        if kind not in ("audio", "image"):
            raise MediaAssetError(f"Invalid kind: {kind!r}; must be 'audio' or 'image'")

        asset_id = uuid.uuid4()
        suffix = Path(filename).suffix or _kind_default_suffix(kind)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = self._storage_dir / f"{asset_id}{suffix}"
        storage_path.write_bytes(data)

        telegram_file_id: str | None = None
        if self._bot is not None and self._chat_id is not None:
            telegram_file_id = await _send_to_telegram(
                self._bot, self._chat_id, data, filename, kind
            )

        asset = MediaAsset(
            id=asset_id,
            kind=kind,
            storage_path=str(storage_path),
            telegram_file_id=telegram_file_id,
            mime=mime,
        )
        await self._repo.create(asset)
        await self._session.commit()
        return asset

    async def list_assets(self, kind: str | None = None) -> list[MediaAsset]:
        """Return all media assets, optionally filtered by kind."""
        return await self._repo.list_all(kind)

    async def get_asset(self, asset_id: uuid.UUID) -> MediaAsset | None:
        """Return a single media asset by UUID, or None."""
        return await self._repo.get(asset_id)

    async def delete_asset(self, asset_id: uuid.UUID) -> bool:
        """Delete a MediaAsset row and its file on disk. Returns False when not found."""
        asset = await self._repo.get(asset_id)
        if asset is None:
            return False
        storage_path = Path(asset.storage_path) if asset.storage_path else None
        await self._repo.delete(asset_id)
        await self._session.commit()
        if storage_path is not None and storage_path.exists():
            storage_path.unlink(missing_ok=True)
        return True

    async def create_motivational_image(
        self,
        media_asset_id: uuid.UUID,
        active: bool = True,
    ) -> MotivationalImage:
        """Add a MediaAsset to the motivational-image pool and commit."""
        asset = await self._repo.get(media_asset_id)
        if asset is None:
            raise MediaAssetError(f"MediaAsset {media_asset_id} not found")
        if asset.kind != "image":
            raise MediaAssetError(
                f"MediaAsset {media_asset_id} has kind={asset.kind!r}; must be 'image'"
            )
        image = MotivationalImage(id=uuid.uuid4(), media_asset_id=media_asset_id, active=active)
        await self._image_repo.save(image)
        await self._session.commit()
        return image


def _kind_default_suffix(kind: str) -> str:
    """Return the default file extension for a given media kind."""
    return ".jpg" if kind == "image" else ".mp3"


async def _send_to_telegram(
    bot: object,
    chat_id: int,
    data: bytes,
    filename: str,
    kind: str,
) -> str | None:
    """Send bytes to Telegram and return the telegram_file_id, or None on failure."""
    from aiogram.types import BufferedInputFile

    input_file = BufferedInputFile(data, filename=filename)
    try:
        if kind == "image":
            msg = await bot.send_photo(chat_id=chat_id, photo=input_file)  # type: ignore[union-attr]
            if msg.photo:
                return msg.photo[-1].file_id
        else:
            msg = await bot.send_audio(chat_id=chat_id, audio=input_file)  # type: ignore[union-attr]
            if msg.audio:
                return msg.audio.file_id
    except Exception:
        pass
    return None
