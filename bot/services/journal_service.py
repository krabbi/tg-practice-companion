"""Service for capturing user replies into the journal."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.exceptions import JournalCaptureError
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository

logger = logging.getLogger(__name__)

# Prompts older than this many hours are considered stale and won't bind to new replies
_PROMPT_EXPIRY_HOURS = 24


@dataclass(frozen=True)
class CaptureResult:
    """Result returned by JournalService.capture."""

    entry_id: uuid.UUID
    needs_assessment: bool
    # The pending_prompt id that was consumed, or None if no prompt was bound
    prompt_id: uuid.UUID | None


class JournalService:
    """Captures user replies into the journal and binds them to pending prompts.

    Binding strategy (Decision B1):
    1. If the incoming message has a reply-to message_id, look up the matching
       unconsumed pending_prompt by telegram_message_id (exact match wins).
    2. Otherwise, fall back to the newest unconsumed prompt not older than
       _PROMPT_EXPIRY_HOURS hours.
    3. If no prompt matches, the entry is stored with practice_id=None.
    """

    def __init__(
        self,
        session: AsyncSession,
        journal_repo: JournalRepository,
        prompt_repo: PendingPromptRepository,
    ) -> None:
        self._session = session
        self._journal_repo = journal_repo
        self._prompt_repo = prompt_repo

    async def capture(
        self,
        *,
        user_id: int,
        text: str,
        source: str,
        reply_to_message_id: int | None = None,
    ) -> CaptureResult:
        """Bind the reply to a pending prompt, create a JournalEntry, consume the prompt.

        Returns CaptureResult with needs_assessment=True when the bound prompt
        kind is 'thought', indicating the handler should show self-assessment buttons.
        """
        try:
            prompt = await self._resolve_prompt(user_id, reply_to_message_id)

            entry = await self._journal_repo.create(
                user_id=user_id,
                text=text,
                source=source,
                practice_id=prompt.practice_id if prompt else None,
            )

            if prompt is not None:
                await self._prompt_repo.mark_consumed(prompt.id)

            await self._session.commit()

            needs_assessment = prompt is not None and prompt.kind == "thought"
            prompt_id = prompt.id if prompt is not None else None
            return CaptureResult(
                entry_id=entry.id,
                needs_assessment=needs_assessment,
                prompt_id=prompt_id,
            )
        except JournalCaptureError:
            raise
        except Exception as exc:
            logger.error("capture: unexpected error for user %s: %s", user_id, exc, exc_info=True)
            raise JournalCaptureError(f"Failed to capture journal entry: {exc}") from exc

    async def _resolve_prompt(self, user_id: int, reply_to_message_id: int | None):  # type: ignore[return]
        """Return the best matching unconsumed pending_prompt, or None."""
        # Exact reply-to match wins (precision binding)
        if reply_to_message_id is not None:
            prompt = await self._prompt_repo.get_by_telegram_message_id(
                user_id, reply_to_message_id
            )
            if prompt is not None:
                return prompt

        # Fall back to newest unconsumed prompt within the expiry window
        not_before = datetime.now(UTC) - timedelta(hours=_PROMPT_EXPIRY_HOURS)
        return await self._prompt_repo.newest_unconsumed(user_id, not_before=not_before)
