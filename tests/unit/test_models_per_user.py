"""Unit tests for per-user user_id columns added in migration 0010.

Covers:
- Models accept user_id on instantiation and after flush.
- The composite (user_id, rotation_order) unique constraint on morning_blessings
  is created in the SQLite in-memory schema.
- Two blessings with the same rotation_order but different user_ids coexist.
"""

import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import MorningBlessing, MotivationalImage
from bot.models.practice import MediaAsset, Practice
from bot.models.user import User

_USER_A = 111111111
_USER_B = 222222222


async def _seed_users(session: AsyncSession) -> None:
    """Insert two minimal User rows to satisfy FK constraints."""
    for uid in (_USER_A, _USER_B):
        session.add(User(telegram_id=uid, language="ru"))
    await session.flush()


@pytest.mark.asyncio
async def test_practice_accepts_user_id(db_session: AsyncSession) -> None:
    """Practice can be created and flushed with a user_id."""
    await _seed_users(db_session)
    p = Practice(
        id=uuid.uuid4(),
        user_id=_USER_A,
        name="test practice",
        content_type="text",
        content="hello",
        periodicity_type="fixed_times",
        schedule_times=["10:00"],
        active=True,
        sort_order=0,
    )
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)

    assert p.user_id == _USER_A


@pytest.mark.asyncio
async def test_media_asset_accepts_user_id(db_session: AsyncSession) -> None:
    """MediaAsset can be created and flushed with a user_id."""
    await _seed_users(db_session)
    asset = MediaAsset(
        id=uuid.uuid4(),
        user_id=_USER_A,
        kind="image",
        storage_path="image/test.jpg",
    )
    db_session.add(asset)
    await db_session.flush()
    await db_session.refresh(asset)

    assert asset.user_id == _USER_A


@pytest.mark.asyncio
async def test_motivational_image_accepts_user_id(db_session: AsyncSession) -> None:
    """MotivationalImage can be created and flushed with a user_id."""
    await _seed_users(db_session)
    asset = MediaAsset(
        id=uuid.uuid4(),
        user_id=_USER_A,
        kind="image",
        storage_path="image/test.jpg",
    )
    db_session.add(asset)
    await db_session.flush()

    img = MotivationalImage(
        id=uuid.uuid4(),
        user_id=_USER_A,
        media_asset_id=asset.id,
        active=True,
    )
    db_session.add(img)
    await db_session.flush()
    await db_session.refresh(img)

    assert img.user_id == _USER_A


@pytest.mark.asyncio
async def test_morning_blessing_accepts_user_id(db_session: AsyncSession) -> None:
    """MorningBlessing can be created and flushed with a user_id."""
    await _seed_users(db_session)
    b = MorningBlessing(
        id=uuid.uuid4(),
        user_id=_USER_A,
        text="Good morning",
        rotation_order=1,
        active=True,
    )
    db_session.add(b)
    await db_session.flush()
    await db_session.refresh(b)

    assert b.user_id == _USER_A


@pytest.mark.asyncio
async def test_morning_blessing_composite_unique_allows_same_rotation_different_users(
    db_session: AsyncSession,
) -> None:
    """Two blessings with identical rotation_order but different user_ids coexist."""
    await _seed_users(db_session)

    b1 = MorningBlessing(
        id=uuid.uuid4(), user_id=_USER_A, text="Blessing A", rotation_order=1, active=True
    )
    b2 = MorningBlessing(
        id=uuid.uuid4(), user_id=_USER_B, text="Blessing B", rotation_order=1, active=True
    )
    db_session.add(b1)
    db_session.add(b2)
    await db_session.flush()
    await db_session.commit()

    # Both rows persisted without constraint violation
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM morning_blessings WHERE rotation_order = 1")
    )
    assert result.scalar() == 2


@pytest.mark.asyncio
async def test_morning_blessing_composite_unique_constraint_exists(
    db_session: AsyncSession,
) -> None:
    """SQLite metadata reflects the composite (user_id, rotation_order) unique constraint."""

    def _get_unique_constraint_columns(sync_conn) -> list[list[str]]:
        inspector = inspect(sync_conn)
        constraints = inspector.get_unique_constraints("morning_blessings")
        return [sorted(c["column_names"]) for c in constraints]

    async with db_session.bind.connect() as conn:  # type: ignore[union-attr]
        all_unique_cols = await conn.run_sync(_get_unique_constraint_columns)

    assert sorted(["rotation_order", "user_id"]) in all_unique_cols
