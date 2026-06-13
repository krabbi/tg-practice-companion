"""Repository for PracticeSend dedup ledger."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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

        Uses INSERT ... ON CONFLICT DO NOTHING so the repository never calls rollback
        (only flush/commit are permitted at this layer). Works with both SQLite
        (aiosqlite, used in unit tests) and PostgreSQL (used in CI and production).
        The dialect is detected from the session's bind at call time.
        """
        bind = self._session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else "sqlite"

        values = {
            "id": uuid.uuid4(),
            "practice_id": practice_id,
            "user_id": user_id,
            "slot_key": slot_key,
            "sent_at": sent_at,
        }

        if dialect_name == "postgresql":
            stmt = (
                pg_insert(PracticeSend)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["practice_id", "slot_key"])
            )
        else:
            # SQLite (and any other dialect that supports the SQLite insert variant)
            stmt = sqlite_insert(PracticeSend).values(**values).on_conflict_do_nothing()

        result = await self._session.execute(stmt)
        # rowcount == 1 means the row was inserted; 0 means the conflict fired (duplicate)
        return result.rowcount == 1

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
