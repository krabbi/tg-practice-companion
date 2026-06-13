"""Repository for PendingPrompt records."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import PendingPrompt


class PendingPromptRepository:
    """CRUD access for PendingPrompt records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        kind: str,
        practice_id: uuid.UUID | None = None,
        telegram_message_id: int | None = None,
    ) -> PendingPrompt:
        """Create and flush a new pending prompt; caller is responsible for commit."""
        prompt = PendingPrompt(
            user_id=user_id,
            kind=kind,
            practice_id=practice_id,
            telegram_message_id=telegram_message_id,
            consumed=False,
            clarify_sent=False,
        )
        self._session.add(prompt)
        await self._session.flush()
        await self._session.refresh(prompt)
        return prompt

    async def get_by_telegram_message_id(
        self, user_id: int, telegram_message_id: int
    ) -> PendingPrompt | None:
        """Return the unconsumed prompt matching the given Telegram message_id, or None."""
        result = await self._session.execute(
            select(PendingPrompt)
            .where(
                PendingPrompt.user_id == user_id,
                PendingPrompt.telegram_message_id == telegram_message_id,
                PendingPrompt.consumed.is_(False),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def newest_unconsumed(
        self, user_id: int, not_before: datetime | None = None
    ) -> PendingPrompt | None:
        """Return the newest unconsumed prompt for *user_id* created at or after *not_before*.

        *not_before* is the staleness cutoff: prompts older than this timestamp
        are excluded (stale prompts cannot capture an unrelated later message).
        Pass ``None`` to skip the cutoff and return the absolute newest prompt.
        """
        stmt = (
            select(PendingPrompt)
            .where(
                PendingPrompt.user_id == user_id,
                PendingPrompt.consumed.is_(False),
            )
            .order_by(PendingPrompt.created_at.desc())
            .limit(1)
        )
        if not_before is not None:
            stmt = stmt.where(PendingPrompt.created_at >= not_before)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_consumed(self, prompt_id: uuid.UUID) -> None:
        """Mark the prompt as consumed; caller is responsible for commit."""
        await self._session.execute(
            update(PendingPrompt).where(PendingPrompt.id == prompt_id).values(consumed=True)
        )

    async def mark_clarify_sent(self, prompt_id: uuid.UUID) -> None:
        """Set clarify_sent=True on the prompt; caller is responsible for commit."""
        await self._session.execute(
            update(PendingPrompt).where(PendingPrompt.id == prompt_id).values(clarify_sent=True)
        )
