"""Integration tests for PracticeSendRepository using aiosqlite :memory: DB.

Covers:
- try_claim: first claim returns True
- try_claim: duplicate claim (conflict) returns False
- exists: returns True when a send row exists, False otherwise
- prune_older_than: deletes rows before cutoff, keeps rows after
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import Practice
from bot.repositories.practice_send_repository import PracticeSendRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_practice_row() -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "send test"
    p.content_type = "text"
    p.content = "hello"
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["10:00"]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = 0
    p.media_asset_id = None
    return p


async def seed_practice(session: AsyncSession) -> Practice:
    p = make_practice_row()
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# try_claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_try_claim_first_time_returns_true(db_session: AsyncSession) -> None:
    """First claim for a (practice_id, slot_key) returns True."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    claimed = await repo.try_claim(
        practice_id=practice.id,
        user_id=123,
        slot_key="2026-06-12T10:00",
        sent_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert claimed is True


@pytest.mark.asyncio
async def test_try_claim_duplicate_returns_false(db_session: AsyncSession) -> None:
    """Second claim for the same (practice_id, slot_key) returns False (conflict)."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    slot = "2026-06-12T10:00"
    sent_at = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)

    first = await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key=slot, sent_at=sent_at
    )
    second = await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key=slot, sent_at=sent_at
    )

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_try_claim_different_slots_both_succeed(db_session: AsyncSession) -> None:
    """Claims for the same practice but different slot_keys both succeed."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    sent_at = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    first = await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key="2026-06-12T10:00", sent_at=sent_at
    )
    second = await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key="2026-06-12T11:00", sent_at=sent_at
    )

    assert first is True
    assert second is True


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exists_returns_true_when_send_row_present(db_session: AsyncSession) -> None:
    """exists returns True after a successful try_claim."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    slot = "2026-06-12T10:00"
    await repo.try_claim(
        practice_id=practice.id,
        user_id=123,
        slot_key=slot,
        sent_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert await repo.exists(practice.id, slot) is True


@pytest.mark.asyncio
async def test_exists_returns_false_when_no_send_row(db_session: AsyncSession) -> None:
    """exists returns False when no send row exists for the slot."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    assert await repo.exists(practice.id, "2026-06-12T10:00") is False


# ---------------------------------------------------------------------------
# prune_older_than
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_older_than_deletes_old_rows(db_session: AsyncSession) -> None:
    """prune_older_than deletes rows with sent_at before the cutoff."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    old_time = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    new_time = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    cutoff = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)

    # Insert one old and one new row
    await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key="2026-05-01T10:00", sent_at=old_time
    )
    await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key="2026-06-12T10:00", sent_at=new_time
    )

    deleted = await repo.prune_older_than(cutoff)

    assert deleted == 1
    # Old slot is gone, new slot remains
    assert await repo.exists(practice.id, "2026-05-01T10:00") is False
    assert await repo.exists(practice.id, "2026-06-12T10:00") is True


@pytest.mark.asyncio
async def test_prune_older_than_returns_zero_when_nothing_to_prune(
    db_session: AsyncSession,
) -> None:
    """prune_older_than returns 0 when all rows are newer than the cutoff."""
    repo = PracticeSendRepository(db_session)
    practice = await seed_practice(db_session)

    new_time = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    cutoff = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)

    await repo.try_claim(
        practice_id=practice.id, user_id=123, slot_key="2026-06-12T10:00", sent_at=new_time
    )

    deleted = await repo.prune_older_than(cutoff)
    assert deleted == 0
