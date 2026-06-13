"""Service for transcribing voice messages via Groq Whisper API."""

import logging

from groq import AsyncGroq

from bot.config import Config

logger = logging.getLogger(__name__)

# Pinned model — matches config.whisper_model default (AC-7)
_WHISPER_MODEL = "whisper-large-v3-turbo"


class TranscriptionService:
    """Transcribe audio bytes to text using Groq Whisper.

    Raw audio bytes are never written to disk or stored in the DB (AC-7).
    The caller provides bytes; this service returns the transcript string.
    """

    def __init__(self, config: Config) -> None:
        self._client = AsyncGroq(api_key=config.groq_api_key)
        self._model = config.whisper_model

    async def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Transcribe *audio_bytes* and return the transcript text.

        *filename* is passed to the Groq API to help it infer the audio format.
        The bytes are never written to disk.
        """
        logger.debug(
            "transcribe: calling Groq Whisper (%s), %d bytes", self._model, len(audio_bytes)
        )

        transcription = await self._client.audio.transcriptions.create(
            model=self._model,
            file=(filename, audio_bytes),
        )
        text: str = transcription.text
        logger.debug("transcribe: got %d chars", len(text))
        return text
