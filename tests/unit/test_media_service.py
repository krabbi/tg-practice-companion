"""Unit tests for MediaAdminService (Stage 2 web admin media upload, B4 / #69).

Covers kind validation, the disk-write + Telegram-capture branches of upload(),
delete (missing / found-with-unlink), the motivational-image pool guards, and the
_send_to_telegram helper (image/audio success + exception fallback).
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.models.practice import MediaAsset
from bot.services.media_service import (
    MediaAdminService,
    MediaAssetError,
    _kind_default_suffix,
    _send_to_telegram,
)


def _make_service(
    tmp_path: Path,
    bot: object | None = None,
    chat_id: int | None = None,
) -> tuple[MediaAdminService, AsyncMock, AsyncMock, AsyncMock]:
    session = AsyncMock()
    repo = AsyncMock()
    image_repo = AsyncMock()
    # create() echoes its argument back, mirroring the real flush+refresh.
    repo.create.side_effect = lambda asset: asset
    image_repo.save.side_effect = lambda image: image
    service = MediaAdminService(
        session=session,
        repo=repo,
        image_repo=image_repo,
        bot=bot,
        chat_id=chat_id,
        storage_dir=tmp_path,
    )
    return service, session, repo, image_repo


def _make_mock_bot(file_id: str = "FAKE_FILE_ID") -> MagicMock:
    bot = MagicMock()
    photo_variant = MagicMock()
    photo_variant.file_id = file_id
    photo_msg = MagicMock()
    photo_msg.photo = [photo_variant]
    bot.send_photo = AsyncMock(return_value=photo_msg)

    audio_obj = MagicMock()
    audio_obj.file_id = file_id
    audio_msg = MagicMock()
    audio_msg.audio = audio_obj
    bot.send_audio = AsyncMock(return_value=audio_msg)
    return bot


async def test_upload_invalid_kind_rejected(tmp_path: Path):
    service, _session, repo, _image_repo = _make_service(tmp_path)

    with pytest.raises(MediaAssetError, match="Invalid kind"):
        await service.upload(b"data", "x.bin", "video", "application/octet-stream")

    repo.create.assert_not_awaited()


async def test_upload_without_bot_writes_file_and_commits(tmp_path: Path):
    service, session, repo, _image_repo = _make_service(tmp_path, bot=None, chat_id=None)

    asset = await service.upload(b"bytes", "pic.png", "image", "image/png")

    assert asset.telegram_file_id is None
    assert Path(asset.storage_path).read_bytes() == b"bytes"
    assert asset.storage_path.endswith(".png")
    repo.create.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_upload_uses_default_suffix_when_filename_has_none(tmp_path: Path):
    service, _session, _repo, _image_repo = _make_service(tmp_path)

    asset = await service.upload(b"x", "noextension", "image", "image/jpeg")

    assert asset.storage_path.endswith(".jpg")


async def test_upload_with_bot_captures_image_file_id(tmp_path: Path):
    bot = _make_mock_bot("PHOTO_ID")
    service, _session, _repo, _image_repo = _make_service(tmp_path, bot=bot, chat_id=42)

    asset = await service.upload(b"img", "p.jpg", "image", "image/jpeg")

    assert asset.telegram_file_id == "PHOTO_ID"
    bot.send_photo.assert_awaited_once()


async def test_list_assets_delegates_to_repo(tmp_path: Path):
    service, _session, repo, _image_repo = _make_service(tmp_path)
    repo.list_all.return_value = ["a", "b"]

    result = await service.list_assets(kind="image")

    assert result == ["a", "b"]
    repo.list_all.assert_awaited_once_with("image")


async def test_get_asset_delegates_to_repo(tmp_path: Path):
    service, _session, repo, _image_repo = _make_service(tmp_path)
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path="/x.jpg")
    repo.get.return_value = asset

    result = await service.get_asset(asset.id)

    assert result is asset
    repo.get.assert_awaited_once_with(asset.id)


async def test_delete_asset_missing_returns_false(tmp_path: Path):
    service, session, repo, _image_repo = _make_service(tmp_path)
    repo.get.return_value = None

    result = await service.delete_asset(uuid.uuid4())

    assert result is False
    repo.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_delete_asset_found_removes_row_and_file(tmp_path: Path):
    service, session, repo, _image_repo = _make_service(tmp_path)
    file_path = tmp_path / "to_delete.jpg"
    file_path.write_bytes(b"x")
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path=str(file_path))
    repo.get.return_value = asset

    result = await service.delete_asset(asset.id)

    assert result is True
    assert not file_path.exists()
    repo.delete.assert_awaited_once_with(asset.id)
    session.commit.assert_awaited_once()


async def test_create_motivational_image_missing_asset_raises(tmp_path: Path):
    service, _session, repo, _image_repo = _make_service(tmp_path)
    repo.get.return_value = None

    with pytest.raises(MediaAssetError, match="not found"):
        await service.create_motivational_image(uuid.uuid4())


async def test_create_motivational_image_wrong_kind_raises(tmp_path: Path):
    service, _session, repo, _image_repo = _make_service(tmp_path)
    repo.get.return_value = MediaAsset(id=uuid.uuid4(), kind="audio", storage_path="/a.mp3")

    with pytest.raises(MediaAssetError, match="must be 'image'"):
        await service.create_motivational_image(uuid.uuid4())


async def test_create_motivational_image_success(tmp_path: Path):
    service, session, repo, image_repo = _make_service(tmp_path)
    asset_id = uuid.uuid4()
    repo.get.return_value = MediaAsset(id=asset_id, kind="image", storage_path="/i.jpg")

    image = await service.create_motivational_image(asset_id, active=False)

    assert image.media_asset_id == asset_id
    assert image.active is False
    image_repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()


def test_kind_default_suffix():
    assert _kind_default_suffix("image") == ".jpg"
    assert _kind_default_suffix("audio") == ".mp3"


async def test_send_to_telegram_audio_returns_file_id():
    bot = _make_mock_bot("AUDIO_ID")

    result = await _send_to_telegram(bot, 1, b"a", "s.mp3", "audio")

    assert result == "AUDIO_ID"
    bot.send_audio.assert_awaited_once()


async def test_send_to_telegram_swallows_exception_and_returns_none():
    bot = MagicMock()
    bot.send_photo = AsyncMock(side_effect=RuntimeError("telegram down"))

    result = await _send_to_telegram(bot, 1, b"a", "p.jpg", "image")

    assert result is None
