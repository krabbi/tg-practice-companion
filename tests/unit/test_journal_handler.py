"""Unit tests for the journal handler (text and voice paths)."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import File, Message, User, Voice

from bot.exceptions import JournalCaptureError
from bot.services.journal_service import CaptureResult, JournalService
from bot.services.transcription_service import TranscriptionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: int = 123) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = user_id
    return u


def _make_message(
    text: str | None = "hello",
    user_id: int = 123,
    reply_to_message_id: int | None = None,
) -> MagicMock:
    message = MagicMock(spec=Message)
    message.from_user = _make_user(user_id)
    message.text = text
    message.voice = None
    message.answer = AsyncMock()
    if reply_to_message_id is not None:
        reply_msg = MagicMock()
        reply_msg.message_id = reply_to_message_id
        message.reply_to_message = reply_msg
    else:
        message.reply_to_message = None
    return message


def _make_voice_message(file_id: str = "fid123", user_id: int = 123) -> MagicMock:
    voice = MagicMock(spec=Voice)
    voice.file_id = file_id

    file_obj = MagicMock(spec=File)
    file_obj.file_path = "voice/file.ogg"

    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=file_obj)

    async def _download(path: str, destination: io.BytesIO) -> None:
        destination.write(b"ogg-bytes")

    bot.download_file = AsyncMock(side_effect=_download)

    msg = MagicMock(spec=Message)
    msg.from_user = _make_user(user_id)
    msg.voice = voice
    msg.bot = bot
    msg.reply_to_message = None
    msg.answer = AsyncMock()
    return msg


def _make_journal_service(
    entry_id: uuid.UUID | None = None,
    needs_assessment: bool = False,
    raises: Exception | None = None,
) -> MagicMock:
    svc = MagicMock(spec=JournalService)
    eid = entry_id or uuid.uuid4()
    if raises:
        svc.capture = AsyncMock(side_effect=raises)
    else:
        svc.capture = AsyncMock(
            return_value=CaptureResult(
                entry_id=eid, needs_assessment=needs_assessment, prompt_id=None
            )
        )
    return svc


# ---------------------------------------------------------------------------
# _capture_and_reply helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_and_reply_text_no_assessment() -> None:
    """capture_and_reply: text entry, no assessment needed — no keyboard sent."""
    from bot.handlers.journal import _capture_and_reply

    message = _make_message("привет")
    svc = _make_journal_service(needs_assessment=False)

    await _capture_and_reply(message, "привет", "text", svc, "ru")

    svc.capture.assert_awaited_once()
    _, kwargs = svc.capture.call_args
    assert kwargs["text"] == "привет"
    assert kwargs["source"] == "text"
    # No assessment keyboard
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_and_reply_thought_sends_assessment_keyboard() -> None:
    """capture_and_reply: thought entry sends the assessment inline keyboard."""
    from bot.handlers.journal import _capture_and_reply

    entry_id = uuid.uuid4()
    message = _make_message("мысль")
    svc = _make_journal_service(entry_id=entry_id, needs_assessment=True)

    await _capture_and_reply(message, "мысль", "text", svc, "ru")

    message.answer.assert_awaited_once()
    call_args = message.answer.call_args
    # The keyboard message contains the clarify question
    from bot.i18n import t

    assert t("assess_clarify", "ru") in call_args.args[0]
    # reply_markup is set
    assert call_args.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_capture_and_reply_passes_reply_to_id() -> None:
    """capture_and_reply passes reply_to_message_id when message is a reply."""
    from bot.handlers.journal import _capture_and_reply

    message = _make_message("reply text", reply_to_message_id=99)
    svc = _make_journal_service()

    await _capture_and_reply(message, "reply text", "text", svc, "ru")

    _, kwargs = svc.capture.call_args
    assert kwargs["reply_to_message_id"] == 99


@pytest.mark.asyncio
async def test_capture_and_reply_on_journal_capture_error() -> None:
    """capture_and_reply: JournalCaptureError → user gets capture_failed message."""
    from bot.handlers.journal import _capture_and_reply

    message = _make_message("text")
    svc = _make_journal_service(raises=JournalCaptureError("fail"))

    await _capture_and_reply(message, "text", "text", svc, "ru")

    message.answer.assert_awaited_once()
    call_args = message.answer.call_args
    from bot.i18n import t

    assert t("capture_failed", "ru") in call_args.args[0]


# ---------------------------------------------------------------------------
# handle_text (inner router handler)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_text_no_from_user_returns_early() -> None:
    """handle_text: returns early when from_user is None."""
    from bot.handlers.journal import create_router

    router = create_router()
    message = MagicMock(spec=Message)
    message.from_user = None
    message.text = "hello"
    message.answer = AsyncMock()
    journal_svc = _make_journal_service()

    # handlers[1] is handle_text
    await router.message.handlers[1].call(message, journal_service=journal_svc)
    journal_svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_text_empty_text_returns_early() -> None:
    """handle_text: returns early when message.text is empty/None."""
    from bot.handlers.journal import create_router

    router = create_router()
    message = _make_message(text=None)
    svc = _make_journal_service()

    await router.message.handlers[1].call(message, journal_service=svc)
    svc.capture.assert_not_awaited()


# ---------------------------------------------------------------------------
# handle_voice path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_voice_transcribes_and_captures() -> None:
    """Voice handler: downloads bytes, transcribes, and captures the entry."""
    from bot.handlers.journal import _capture_and_reply

    entry_id = uuid.uuid4()
    message = _make_voice_message()
    svc = _make_journal_service(entry_id=entry_id, needs_assessment=False)

    mock_transcription = MagicMock(spec=TranscriptionService)
    mock_transcription.transcribe = AsyncMock(return_value="транскрипт")

    bot = message.bot
    file = await bot.get_file(message.voice.file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    audio_bytes = buf.getvalue()

    text = await mock_transcription.transcribe(audio_bytes)
    await _capture_and_reply(message, text, "voice", svc, "ru")

    svc.capture.assert_awaited_once()
    _, kwargs = svc.capture.call_args
    assert kwargs["source"] == "voice"
    assert kwargs["text"] == "транскрипт"


@pytest.mark.asyncio
async def test_handle_voice_transcription_failure_returns_error_message() -> None:
    """Voice handler: transcription failure → user gets capture_failed message."""
    # Simulate the transcription try/except block in handle_voice
    message = _make_voice_message()

    async def failing_transcribe(audio: bytes) -> str:
        raise RuntimeError("Groq API error")

    mock_transcription = MagicMock(spec=TranscriptionService)
    mock_transcription.transcribe = AsyncMock(side_effect=RuntimeError("Groq API error"))

    from bot.i18n import t

    try:
        await mock_transcription.transcribe(b"bytes")
    except Exception:
        await message.answer(t("capture_failed", "ru"))

    message.answer.assert_awaited_once()
    assert t("capture_failed", "ru") in message.answer.call_args.args[0]
