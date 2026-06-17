"""Unit tests for BlessingRepository (SQLite in-memory).

Covers the methods that were uncovered after the B6 integration tests:
list_all, create, update, delete, and reorder.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.blessing_repository import BlessingRepository


@pytest.mark.asyncio
async def test_blessing_list_all_returns_ordered(db_session: AsyncSession) -> None:
    """list_all returns all blessings sorted by rotation_order ascending."""
    repo = BlessingRepository(db_session)

    b3 = await repo.create(text="Third", rotation_order=3)
    b1 = await repo.create(text="First", rotation_order=1)
    b2 = await repo.create(text="Second", rotation_order=2)
    await db_session.commit()

    result = await repo.list_all()

    assert len(result) == 3
    assert result[0].id == b1.id
    assert result[1].id == b2.id
    assert result[2].id == b3.id


@pytest.mark.asyncio
async def test_blessing_list_all_empty(db_session: AsyncSession) -> None:
    """list_all returns empty list when no blessings exist."""
    repo = BlessingRepository(db_session)
    result = await repo.list_all()
    assert result == []


@pytest.mark.asyncio
async def test_blessing_create(db_session: AsyncSession) -> None:
    """create flushes and returns a blessing with the given fields."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="Good morning", rotation_order=1, active=True)
    await db_session.commit()

    assert b.id is not None
    assert b.text == "Good morning"
    assert b.rotation_order == 1
    assert b.active is True


@pytest.mark.asyncio
async def test_blessing_create_inactive(db_session: AsyncSession) -> None:
    """create respects active=False."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="Inactive", rotation_order=1, active=False)
    await db_session.commit()

    fetched = await repo.get_by_id(b.id)
    assert fetched is not None
    assert fetched.active is False


@pytest.mark.asyncio
async def test_blessing_update_text(db_session: AsyncSession) -> None:
    """update changes text field and returns the updated row."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="Original", rotation_order=1)
    await db_session.commit()

    updated = await repo.update(b.id, text="Updated")
    await db_session.commit()

    assert updated is not None
    assert updated.text == "Updated"
    assert updated.rotation_order == 1


@pytest.mark.asyncio
async def test_blessing_update_active(db_session: AsyncSession) -> None:
    """update changes active field and returns the updated row."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="Active blessing", rotation_order=1, active=True)
    await db_session.commit()

    updated = await repo.update(b.id, active=False)
    await db_session.commit()

    assert updated is not None
    assert updated.active is False
    assert updated.text == "Active blessing"


@pytest.mark.asyncio
async def test_blessing_update_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """update returns None when the id does not exist."""
    repo = BlessingRepository(db_session)
    result = await repo.update(uuid.uuid4(), text="x")
    assert result is None


@pytest.mark.asyncio
async def test_blessing_delete(db_session: AsyncSession) -> None:
    """delete removes the row and returns True."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="To delete", rotation_order=1)
    await db_session.commit()

    deleted = await repo.delete(b.id)
    await db_session.commit()

    assert deleted is True
    assert await repo.get_by_id(b.id) is None


@pytest.mark.asyncio
async def test_blessing_delete_returns_false_for_unknown(db_session: AsyncSession) -> None:
    """delete returns False when the id does not exist."""
    repo = BlessingRepository(db_session)
    result = await repo.delete(uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_blessing_reorder(db_session: AsyncSession) -> None:
    """reorder assigns rotation_order 1..N in the supplied order."""
    repo = BlessingRepository(db_session)

    b1 = await repo.create(text="A", rotation_order=1)
    b2 = await repo.create(text="B", rotation_order=2)
    b3 = await repo.create(text="C", rotation_order=3)
    await db_session.commit()

    # Reverse the order
    result = await repo.reorder([b3.id, b1.id, b2.id])
    await db_session.commit()

    assert len(result) == 3
    assert result[0].id == b3.id
    assert result[0].rotation_order == 1
    assert result[1].id == b1.id
    assert result[1].rotation_order == 2
    assert result[2].id == b2.id
    assert result[2].rotation_order == 3


@pytest.mark.asyncio
async def test_blessing_reorder_raises_for_unknown_id(db_session: AsyncSession) -> None:
    """reorder raises KeyError if any supplied id does not exist."""
    repo = BlessingRepository(db_session)

    b = await repo.create(text="A", rotation_order=1)
    await db_session.commit()

    with pytest.raises(KeyError):
        await repo.reorder([b.id, uuid.uuid4()])
