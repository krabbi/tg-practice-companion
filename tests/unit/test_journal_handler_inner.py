"""Tests for handle_voice and handle_text inner closures in journal.create_router().

These tests invoke the handlers via router.message.handlers[i].call() to
exercise lines 53-77 and 85-88 that are unreachable from _capture_and_reply alone.
"""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import File, Message, User, Voice

from bot.services.journal_service import CaptureResult, JournalService
from bot.services.transcription_service import TranscriptionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: int = 123) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = user_id
    return u


def _make_text_message(text: str = "hello", reply_to_id: int | None = None) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = _make_user()
    msg.text = text
    msg.voice = None
    msg.answer = AsyncMock()
    if reply_to_id is not None:
        reply = MagicMock()
        reply.message_id = reply_to_id
        msg.reply_to_message = reply
    else:
        msg.reply_to_message = None
    return msg


def _make_voice_message(
    file_id: str = "fid",
    audio_content: bytes = b"ogg",
    user_id: int = 123,
) -> MagicMock:
    voice = MagicMock(spec=Voice)
    voice.file_id = file_id

    file_obj = MagicMock(spec=File)
    file_obj.file_path = "voice/f.ogg"

    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=file_obj)

    async def _dl(path: str, destination: io.BytesIO) -> None:
        destination.write(audio_content)

    bot.download_file = AsyncMock(side_effect=_dl)

    msg = MagicMock(spec=Message)
    msg.from_user = _make_user(user_id)
    msg.voice = voice
    msg.bot = bot
    msg.reply_to_message = None
    msg.answer = AsyncMock()
    return msg


def _make_journal_svc(
    needs_assessment: bool = False,
    raises: Exception | None = None,
) -> MagicMock:
    svc = MagicMock(spec=JournalService)
    if raises:
        svc.capture = AsyncMock(side_effect=raises)
    else:
        svc.capture = AsyncMock(
            return_value=CaptureResult(
                entry_id=uuid.uuid4(),
                needs_assessment=needs_assessment,
                prompt_id=None,
            )
        )
    return svc


def _get_handlers(router):  # type: ignore[no-untyped-def]
    """Return the list of message handlers from the router."""
    return list(router.message.handlers)


# ---------------------------------------------------------------------------
# handle_voice (handler index 0 — registered first)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_voice_no_from_user_returns_early() -> None:
    """handle_voice: returns early when from_user is None."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_voice_message()
    msg.from_user = None
    svc = _make_journal_svc()
    ts = MagicMock(spec=TranscriptionService)
    ts.transcribe = AsyncMock(return_value="text")

    handlers = _get_handlers(router)
    await handlers[0].call(msg, journal_service=svc, transcription_service=ts)

    ts.transcribe.assert_not_awaited()
    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_voice_no_voice_returns_early() -> None:
    """handle_voice: returns early when message.voice is None."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_voice_message()
    msg.voice = None
    svc = _make_journal_svc()
    ts = MagicMock(spec=TranscriptionService)
    ts.transcribe = AsyncMock(return_value="text")

    handlers = _get_handlers(router)
    await handlers[0].call(msg, journal_service=svc, transcription_service=ts)

    ts.transcribe.assert_not_awaited()
    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_voice_no_transcription_service_replies_not_configured() -> None:
    """handle_voice: transcription_service=None → voice_not_configured message."""
    from bot.handlers.journal import create_router
    from bot.i18n import t

    router = create_router()
    msg = _make_voice_message()
    svc = _make_journal_svc()

    handlers = _get_handlers(router)
    await handlers[0].call(msg, journal_service=svc, transcription_service=None)

    msg.answer.assert_awaited_once()
    assert t("voice_not_configured", "ru") in msg.answer.call_args.args[0]
    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_voice_transcription_failure_replies_capture_failed() -> None:
    """handle_voice: Groq error → capture_failed message; capture not called."""
    from bot.handlers.journal import create_router
    from bot.i18n import t

    router = create_router()
    msg = _make_voice_message()
    svc = _make_journal_svc()
    ts = MagicMock(spec=TranscriptionService)
    ts.transcribe = AsyncMock(side_effect=RuntimeError("groq down"))

    handlers = _get_handlers(router)
    await handlers[0].call(msg, journal_service=svc, transcription_service=ts)

    msg.answer.assert_awaited_once()
    assert t("capture_failed", "ru") in msg.answer.call_args.args[0]
    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_voice_happy_path_calls_capture() -> None:
    """handle_voice: transcribes and calls journal_service.capture with source=voice."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_voice_message()
    svc = _make_journal_svc()
    ts = MagicMock(spec=TranscriptionService)
    ts.transcribe = AsyncMock(return_value="распознанный текст")

    handlers = _get_handlers(router)
    await handlers[0].call(msg, journal_service=svc, transcription_service=ts)

    ts.transcribe.assert_awaited_once()
    svc.capture.assert_awaited_once()
    _, kwargs = svc.capture.call_args
    assert kwargs["source"] == "voice"
    assert kwargs["text"] == "распознанный текст"


# ---------------------------------------------------------------------------
# handle_text (handler index 1 — registered second)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_text_no_from_user_returns_early() -> None:
    """handle_text: returns early when from_user is None."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_text_message("hello")
    msg.from_user = None
    svc = _make_journal_svc()

    handlers = _get_handlers(router)
    await handlers[1].call(msg, journal_service=svc)

    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_text_empty_text_returns_early() -> None:
    """handle_text: returns early when message.text is None/empty."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_text_message()
    msg.text = None
    svc = _make_journal_svc()

    handlers = _get_handlers(router)
    await handlers[1].call(msg, journal_service=svc)

    svc.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_text_happy_path_calls_capture() -> None:
    """handle_text: calls journal_service.capture with source=text."""
    from bot.handlers.journal import create_router

    router = create_router()
    msg = _make_text_message("мысль")
    svc = _make_journal_svc()

    handlers = _get_handlers(router)
    await handlers[1].call(msg, journal_service=svc)

    svc.capture.assert_awaited_once()
    _, kwargs = svc.capture.call_args
    assert kwargs["source"] == "text"
    assert kwargs["text"] == "мысль"


@pytest.mark.asyncio
async def test_handle_text_thought_sends_assessment_keyboard() -> None:
    """handle_text: thought entry sends assessment keyboard."""
    from bot.handlers.journal import create_router
    from bot.i18n import t

    router = create_router()
    msg = _make_text_message("мысль")
    svc = _make_journal_svc(needs_assessment=True)

    handlers = _get_handlers(router)
    await handlers[1].call(msg, journal_service=svc)

    msg.answer.assert_awaited_once()
    assert t("assess_clarify", "ru") in msg.answer.call_args.args[0]
    assert msg.answer.call_args.kwargs.get("reply_markup") is not None
