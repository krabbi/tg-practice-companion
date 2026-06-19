"""Unit tests for DeliveryService — content_type dispatch and error handling (AC-2)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.exceptions import DeliveryError
from bot.models.practice import MediaAsset, Practice
from bot.services.delivery_service import DeliveryService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_practice(
    content_type: str = "text",
    content: str | None = "hello",
    media_asset: MediaAsset | None = None,
) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "delivery test"
    p.content_type = content_type
    p.content = content
    p.media_asset = media_asset
    p.media_asset_id = media_asset.id if media_asset else None
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["08:00"]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = 0
    return p


def make_asset(kind: str = "audio", telegram_file_id: str | None = "BQACAgI_file123") -> MediaAsset:
    a = MediaAsset()
    a.id = uuid.uuid4()
    a.kind = kind
    a.telegram_file_id = telegram_file_id
    a.storage_path = None
    a.mime = "audio/mpeg"
    return a


def make_service() -> tuple[DeliveryService, MagicMock]:
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_audio = AsyncMock()
    mock_bot.send_photo = AsyncMock()
    mock_bot.send_video = AsyncMock()
    return DeliveryService(mock_bot), mock_bot


USER_ID = 123456789


# ---------------------------------------------------------------------------
# text / question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_practice_calls_send_message() -> None:
    svc, bot = make_service()
    p = make_practice(content_type="text", content="Think positive!")
    await svc.send(p, USER_ID)
    bot.send_message.assert_awaited_once_with(chat_id=USER_ID, text="Think positive!")
    bot.send_audio.assert_not_awaited()
    bot.send_photo.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_practice_calls_send_message() -> None:
    svc, bot = make_service()
    p = make_practice(content_type="question", content="What are you thinking?")
    await svc.send(p, USER_ID)
    bot.send_message.assert_awaited_once_with(chat_id=USER_ID, text="What are you thinking?")


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_practice_calls_send_audio_with_unchanged_file_id() -> None:
    """Audio practice must call send_audio with the stored telegram_file_id unchanged (AC-2)."""
    svc, bot = make_service()
    asset = make_asset(kind="audio", telegram_file_id="BQACAgI_audio_xyz")
    p = make_practice(content_type="audio", media_asset=asset)
    await svc.send(p, USER_ID)
    bot.send_audio.assert_awaited_once_with(chat_id=USER_ID, audio="BQACAgI_audio_xyz")
    bot.send_photo.assert_not_awaited()
    bot.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_practice_calls_send_photo_with_unchanged_file_id() -> None:
    """Image practice must call send_photo with the stored telegram_file_id unchanged (AC-2)."""
    svc, bot = make_service()
    asset = make_asset(kind="image", telegram_file_id="AgACAgI_photo_abc")
    p = make_practice(content_type="image", media_asset=asset)
    await svc.send(p, USER_ID)
    bot.send_photo.assert_awaited_once_with(chat_id=USER_ID, photo="AgACAgI_photo_abc")
    bot.send_audio.assert_not_awaited()
    bot.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# video
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_video_practice_calls_send_video_with_unchanged_file_id() -> None:
    """Video practice must call send_video with the stored telegram_file_id unchanged (AC-2)."""
    svc, bot = make_service()
    asset = make_asset(kind="video", telegram_file_id="BAACAgI_video_xyz")
    p = make_practice(content_type="video", media_asset=asset)
    await svc.send(p, USER_ID)
    bot.send_video.assert_awaited_once_with(chat_id=USER_ID, video="BAACAgI_video_xyz")
    bot.send_audio.assert_not_awaited()
    bot.send_photo.assert_not_awaited()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_missing_media_asset_raises_delivery_error() -> None:
    svc, _ = make_service()
    p = make_practice(content_type="video", media_asset=None)
    with pytest.raises(DeliveryError):
        await svc.send(p, USER_ID)


@pytest.mark.asyncio
async def test_video_missing_telegram_file_id_raises_delivery_error() -> None:
    svc, _ = make_service()
    asset = make_asset(kind="video", telegram_file_id=None)
    p = make_practice(content_type="video", media_asset=asset)
    with pytest.raises(DeliveryError):
        await svc.send(p, USER_ID)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_missing_media_asset_raises_delivery_error() -> None:
    svc, _ = make_service()
    p = make_practice(content_type="audio", media_asset=None)
    with pytest.raises(DeliveryError):
        await svc.send(p, USER_ID)


@pytest.mark.asyncio
async def test_audio_missing_telegram_file_id_raises_delivery_error() -> None:
    svc, _ = make_service()
    asset = make_asset(kind="audio", telegram_file_id=None)
    p = make_practice(content_type="audio", media_asset=asset)
    with pytest.raises(DeliveryError):
        await svc.send(p, USER_ID)


@pytest.mark.asyncio
async def test_send_failure_raises_delivery_error() -> None:
    """A TelegramAPIError from send_message is wrapped in DeliveryError."""
    svc, bot = make_service()
    bot.send_message = AsyncMock(side_effect=Exception("TelegramBadRequest: file not found"))
    p = make_practice(content_type="text", content="hello")
    with pytest.raises(DeliveryError):
        await svc.send(p, USER_ID)
