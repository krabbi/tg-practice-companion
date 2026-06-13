"""Repository for PracticeSend dedup ledger."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import PracticeSend


class PracticeSendRepository:
    """CRUD access for PracticeSend records (the idempotency dedup ledger)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def try_claim(
        self,
        practice_id: uuid.UUID,
        user_id: int,
        slot_key: str,
        sent_at: datetime,
    ) -> bool:
        """Attempt to claim a (practice_id, slot_key) slot.

        Returns True if the slot was newly claimed (the practice should be sent),
        False if it was already claimed (the practice was already sent for this slot).
        The unique index uq_practice_send enforces idempotency — a duplicate INSERT
        raises IntegrityError which we catch and convert to False.
        """
        record = PracticeSend(
            practice_id=practice_id,
            user_id=user_id,
            slot_key=slot_key,
            sent_at=sent_at,
        )
        try:
            self._session.add(record)
            await self._session.flush()
            return True
        except IntegrityError:
            await self._session.rollback()
            return False

    async def exists(self, practice_id: uuid.UUID, slot_key: str) -> bool:
        """Return True if a send record already exists for this practice + slot."""
        result = await self._session.execute(
            select(PracticeSend).where(
                PracticeSend.practice_id == practice_id,
                PracticeSend.slot_key == slot_key,
            )
        )
        return result.scalar_one_or_none() is not None

    async def prune_older_than(self, cutoff: datetime) -> int:
        """Delete all PracticeSend rows whose sent_at is before cutoff.

        Returns the number of rows deleted.
        """
        result = await self._session.execute(
            delete(PracticeSend).where(PracticeSend.sent_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]
