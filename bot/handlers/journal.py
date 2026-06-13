"""Journal capture handler — catch-all for text and voice replies (AC-6, AC-7)."""

import io
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.exceptions import JournalCaptureError
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.journal_service import JournalService
from bot.services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)


def _assessment_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    """Build the yes/no self-assessment inline keyboard for a journal entry."""
    lang = DEFAULT_LANGUAGE
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("assess_yes", lang),
                    callback_data=f"assess:{entry_id}:yes",
                ),
                InlineKeyboardButton(
                    text=t("assess_no", lang),
                    callback_data=f"assess:{entry_id}:no",
                ),
            ]
        ]
    )


def create_router() -> Router:
    """Create and return the journal router.

    Both handlers carry StateFilter(None) so they yield control to any active
    FSM state (e.g. TimezoneSetupStates in M5) — journal capture must never
    swallow first-run setup input.
    """
    router = Router(name="journal")

    @router.message(StateFilter(None), F.voice)
    async def handle_voice(
        message: Message,
        journal_service: JournalService,
        transcription_service: TranscriptionService | None = None,
    ) -> None:
        """Transcribe a voice message and capture it in the journal."""
        if message.from_user is None or message.voice is None:
            return
        lang = DEFAULT_LANGUAGE

        if transcription_service is None:
            await message.answer(t("voice_not_configured", lang))
            return

        # Download audio bytes — never written to disk (AC-7)
        bot = message.bot
        assert bot is not None
        file = await bot.get_file(message.voice.file_id)
        assert file.file_path is not None
        buf = io.BytesIO()
        await bot.download_file(file.file_path, destination=buf)
        audio_bytes = buf.getvalue()

        try:
            text = await transcription_service.transcribe(audio_bytes)
        except Exception:
            logger.exception("handle_voice: transcription failed for user %s", message.from_user.id)
            await message.answer(t("capture_failed", lang))
            return

        await _capture_and_reply(message, text, "voice", journal_service, lang)

    @router.message(StateFilter(None), F.text)
    async def handle_text(
        message: Message,
        journal_service: JournalService,
    ) -> None:
        """Capture a text reply in the journal."""
        if message.from_user is None or not message.text:
            return
        lang = DEFAULT_LANGUAGE
        await _capture_and_reply(message, message.text, "text", journal_service, lang)

    return router


async def _capture_and_reply(
    message: Message,
    text: str,
    source: str,
    journal_service: JournalService,
    lang: str,
) -> None:
    """Shared capture logic for both text and voice paths."""
    assert message.from_user is not None

    reply_to_id: int | None = None
    if message.reply_to_message is not None:
        reply_to_id = message.reply_to_message.message_id

    try:
        result = await journal_service.capture(
            user_id=message.from_user.id,
            text=text,
            source=source,
            reply_to_message_id=reply_to_id,
        )
    except JournalCaptureError:
        logger.exception("_capture_and_reply: capture failed for user %s", message.from_user.id)
        await message.answer(t("capture_failed", lang))
        return

    if result.needs_assessment:
        await message.answer(
            t("assess_clarify", lang),
            reply_markup=_assessment_keyboard(str(result.entry_id)),
        )
