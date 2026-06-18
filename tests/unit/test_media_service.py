"""Unit tests for MediaAdminService (S3 upload path, S2 / #101).

Covers kind validation, S3 put + Telegram-capture branches, orphan-cleanup on
Telegram failure, delete (missing / found), the motivational-image pool guards,
and the _send_to_telegram helper.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.models.practice import MediaAsset
from bot.services.media_service import (
    MediaAdminService,
    MediaAssetError,
    _kind_default_suffix,
    _send_to_telegram,
)
from bot.services.storage_service import S3StorageService

_USER_ID = 123456789


def _make_storage() -> S3StorageService:
    storage = MagicMock(spec=S3StorageService)
    storage.put_object = AsyncMock()
    storage.delete_object = AsyncMock()
    return storage


def _make_service(
    bot: object | None = None,
    chat_id: int | None = None,
    storage: S3StorageService | None = None,
) -> tuple[MediaAdminService, AsyncMock, AsyncMock, AsyncMock, S3StorageService]:
    session = AsyncMock()
    repo = AsyncMock()
    image_repo = AsyncMock()
    repo.create.side_effect = lambda asset: asset
    image_repo.save.side_effect = lambda image: image
    s3 = storage if storage is not None else _make_storage()
    service = MediaAdminService(
        session=session,
        repo=repo,
        image_repo=image_repo,
        bot=bot,
        chat_id=chat_id,
        storage=s3,
    )
    return service, session, repo, image_repo, s3


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


async def test_upload_invalid_kind_rejected():
    service, _session, repo, _image_repo, s3 = _make_service()

    with pytest.raises(MediaAssetError, match="Invalid kind"):
        await service.upload(
            b"data", "x.bin", "video", "application/octet-stream", user_id=_USER_ID
        )

    repo.create.assert_not_awaited()
    s3.put_object.assert_not_awaited()


async def test_upload_without_bot_calls_put_object_and_commits():
    service, session, repo, _image_repo, s3 = _make_service(bot=None, chat_id=None)

    asset = await service.upload(b"bytes", "pic.png", "image", "image/png", user_id=_USER_ID)

    s3.put_object.assert_awaited_once()
    call_key, call_data = s3.put_object.call_args[0][:2]
    assert call_key.startswith("image/")
    assert call_key.endswith(".png")
    assert call_data == b"bytes"
    assert asset.telegram_file_id is None
    assert asset.storage_path == call_key
    assert asset.user_id == _USER_ID
    repo.create.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_upload_no_filesystem_writes():
    """Confirm no Path.write_bytes or mkdir calls happen."""
    service, _session, _repo, _image_repo, _s3 = _make_service()

    with patch("bot.services.media_service.Path") as mock_path_cls:
        mock_path_cls.return_value = MagicMock(suffix=".jpg")
        await service.upload(b"x", "pic.jpg", "image", "image/jpeg", user_id=_USER_ID)

    # write_bytes should never have been called
    for call in mock_path_cls.return_value.mock_calls:
        assert "write_bytes" not in str(call)
        assert "mkdir" not in str(call)


async def test_upload_key_format():
    service, _session, _repo, _image_repo, s3 = _make_service()

    asset = await service.upload(b"x", "track.mp3", "audio", "audio/mpeg", user_id=_USER_ID)

    assert asset.storage_path.startswith("audio/")
    assert asset.storage_path.endswith(".mp3")


async def test_upload_uses_default_suffix_when_filename_has_none():
    service, _session, _repo, _image_repo, s3 = _make_service()

    asset = await service.upload(b"x", "noextension", "image", "image/jpeg", user_id=_USER_ID)

    assert asset.storage_path.endswith(".jpg")


async def test_upload_with_bot_captures_image_file_id():
    bot = _make_mock_bot("PHOTO_ID")
    service, _session, _repo, _image_repo, s3 = _make_service(bot=bot, chat_id=42)

    asset = await service.upload(b"img", "p.jpg", "image", "image/jpeg", user_id=_USER_ID)

    assert asset.telegram_file_id == "PHOTO_ID"
    bot.send_photo.assert_awaited_once()
    s3.put_object.assert_awaited_once()


async def test_upload_put_object_receives_correct_mime():
    service, _session, _repo, _image_repo, s3 = _make_service()

    await service.upload(b"data", "audio.mp3", "audio", "audio/mpeg", user_id=_USER_ID)

    _, kwargs = s3.put_object.call_args
    # content_type is passed as keyword arg
    assert kwargs.get("content_type") == "audio/mpeg"


async def test_upload_orphan_cleanup_on_telegram_failure():
    """If Telegram raises after S3 PUT, delete_object is called and exception re-raised."""
    bot = MagicMock()
    bot.send_photo = AsyncMock(side_effect=RuntimeError("telegram down"))
    service, _session, repo, _image_repo, s3 = _make_service(bot=bot, chat_id=1)

    with pytest.raises(RuntimeError, match="telegram down"):
        await service.upload(b"img", "p.jpg", "image", "image/jpeg", user_id=_USER_ID)

    s3.put_object.assert_awaited_once()
    s3.delete_object.assert_awaited_once()
    # The S3 key passed to delete_object should match what was PUT
    put_key = s3.put_object.call_args[0][0]
    delete_key = s3.delete_object.call_args[0][0]
    assert put_key == delete_key
    # No DB row committed
    repo.create.assert_not_awaited()


async def test_upload_s3_failure_does_not_call_telegram():
    """If S3 PUT fails, Telegram is never called and no row is created."""
    bot = _make_mock_bot()
    service, _session, repo, _image_repo, s3 = _make_service(bot=bot, chat_id=1)
    s3.put_object.side_effect = RuntimeError("S3 down")

    with pytest.raises(RuntimeError, match="S3 down"):
        await service.upload(b"img", "p.jpg", "image", "image/jpeg", user_id=_USER_ID)

    bot.send_photo.assert_not_awaited()
    repo.create.assert_not_awaited()


async def test_list_assets_delegates_to_repo():
    service, _session, repo, _image_repo, _s3 = _make_service()
    repo.list_all.return_value = ["a", "b"]

    result = await service.list_assets(kind="image")

    assert result == ["a", "b"]
    repo.list_all.assert_awaited_once_with("image")


async def test_get_asset_delegates_to_repo():
    service, _session, repo, _image_repo, _s3 = _make_service()
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path="image/x.jpg")
    repo.get.return_value = asset

    result = await service.get_asset(asset.id)

    assert result is asset
    repo.get.assert_awaited_once_with(asset.id)


async def test_delete_asset_missing_returns_false():
    service, session, repo, _image_repo, s3 = _make_service()
    repo.get.return_value = None

    result = await service.delete_asset(uuid.uuid4())

    assert result is False
    repo.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
    s3.delete_object.assert_not_awaited()


async def test_delete_asset_found_removes_row_and_calls_delete_object():
    service, session, repo, _image_repo, s3 = _make_service()
    asset_key = "image/some-uuid.jpg"
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path=asset_key)
    repo.get.return_value = asset

    result = await service.delete_asset(asset.id)

    assert result is True
    repo.delete.assert_awaited_once_with(asset.id)
    session.commit.assert_awaited_once()
    s3.delete_object.assert_awaited_once_with(asset_key)


async def test_delete_asset_s3_failure_is_swallowed():
    """delete_object failure must not propagate — best-effort only."""
    service, session, repo, _image_repo, s3 = _make_service()
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path="image/x.jpg")
    repo.get.return_value = asset
    s3.delete_object.side_effect = RuntimeError("S3 down")

    result = await service.delete_asset(asset.id)

    assert result is True
    session.commit.assert_awaited_once()


async def test_delete_asset_skips_s3_when_storage_path_none():
    service, session, repo, _image_repo, s3 = _make_service()
    asset = MediaAsset(id=uuid.uuid4(), kind="image", storage_path=None)
    repo.get.return_value = asset

    result = await service.delete_asset(asset.id)

    assert result is True
    s3.delete_object.assert_not_awaited()


async def test_create_motivational_image_missing_asset_raises():
    service, _session, repo, _image_repo, _s3 = _make_service()
    repo.get.return_value = None

    with pytest.raises(MediaAssetError, match="not found"):
        await service.create_motivational_image(uuid.uuid4(), _USER_ID)


async def test_create_motivational_image_wrong_kind_raises():
    service, _session, repo, _image_repo, _s3 = _make_service()
    repo.get.return_value = MediaAsset(id=uuid.uuid4(), kind="audio", storage_path="audio/a.mp3")

    with pytest.raises(MediaAssetError, match="must be 'image'"):
        await service.create_motivational_image(uuid.uuid4(), _USER_ID)


async def test_create_motivational_image_success():
    service, session, repo, image_repo, _s3 = _make_service()
    asset_id = uuid.uuid4()
    repo.get.return_value = MediaAsset(id=asset_id, kind="image", storage_path="image/i.jpg")

    image = await service.create_motivational_image(asset_id, _USER_ID, active=False)

    assert image.media_asset_id == asset_id
    assert image.user_id == _USER_ID
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


async def test_send_to_telegram_image_returns_file_id():
    bot = _make_mock_bot("PHOTO_ID")

    result = await _send_to_telegram(bot, 1, b"a", "p.jpg", "image")

    assert result == "PHOTO_ID"
    bot.send_photo.assert_awaited_once()


async def test_send_to_telegram_propagates_exception():
    """_send_to_telegram no longer swallows exceptions — caller handles cleanup."""
    bot = MagicMock()
    bot.send_photo = AsyncMock(side_effect=RuntimeError("telegram down"))

    with pytest.raises(RuntimeError, match="telegram down"):
        await _send_to_telegram(bot, 1, b"a", "p.jpg", "image")
