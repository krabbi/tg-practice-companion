"""Unit tests for BlessingRepository (SQLite in-memory).

Covers the methods that were uncovered after the B6 integration tests:
list_all, create, update, delete, and reorder — all scoped to user_id.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.repositories.blessing_repository import BlessingRepository

_USER_ID = 123456789
_OTHER_USER_ID = 999888777


async def _seed_user(session: AsyncSession, telegram_id: int = _USER_ID) -> None:
    """Insert a minimal User row so FK constraints on user_id are satisfied."""
    user = User(telegram_id=telegram_id, language="ru")
    session.add(user)
    await session.flush()


@pytest.mark.asyncio
async def test_blessing_list_all_returns_ordered(db_session: AsyncSession) -> None:
    """list_all returns all blessings sorted by rotation_order ascending."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b3 = await repo.create(user_id=_USER_ID, text="Third", rotation_order=3)
    b1 = await repo.create(user_id=_USER_ID, text="First", rotation_order=1)
    b2 = await repo.create(user_id=_USER_ID, text="Second", rotation_order=2)
    await db_session.commit()

    result = await repo.list_all(_USER_ID)

    assert len(result) == 3
    assert result[0].id == b1.id
    assert result[1].id == b2.id
    assert result[2].id == b3.id


@pytest.mark.asyncio
async def test_blessing_list_all_empty(db_session: AsyncSession) -> None:
    """list_all returns empty list when no blessings exist."""
    repo = BlessingRepository(db_session)
    result = await repo.list_all(_USER_ID)
    assert result == []


@pytest.mark.asyncio
async def test_blessing_list_all_user_isolation(db_session: AsyncSession) -> None:
    """list_all returns only blessings for the given user."""
    await _seed_user(db_session, _USER_ID)
    await _seed_user(db_session, _OTHER_USER_ID)
    repo = BlessingRepository(db_session)

    await repo.create(user_id=_USER_ID, text="Mine", rotation_order=1)
    await repo.create(user_id=_OTHER_USER_ID, text="Other", rotation_order=1)
    await db_session.commit()

    result = await repo.list_all(_USER_ID)
    assert len(result) == 1
    assert result[0].text == "Mine"


@pytest.mark.asyncio
async def test_blessing_create(db_session: AsyncSession) -> None:
    """create flushes and returns a blessing with the given fields."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="Good morning", rotation_order=1, active=True)
    await db_session.commit()

    assert b.id is not None
    assert b.user_id == _USER_ID
    assert b.text == "Good morning"
    assert b.rotation_order == 1
    assert b.active is True


@pytest.mark.asyncio
async def test_blessing_create_inactive(db_session: AsyncSession) -> None:
    """create respects active=False."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="Inactive", rotation_order=1, active=False)
    await db_session.commit()

    fetched = await repo.get_by_id(b.id)
    assert fetched is not None
    assert fetched.active is False


@pytest.mark.asyncio
async def test_blessing_update_text(db_session: AsyncSession) -> None:
    """update changes text field and returns the updated row."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="Original", rotation_order=1)
    await db_session.commit()

    updated = await repo.update(b.id, _USER_ID, text="Updated")
    await db_session.commit()

    assert updated is not None
    assert updated.text == "Updated"
    assert updated.rotation_order == 1


@pytest.mark.asyncio
async def test_blessing_update_active(db_session: AsyncSession) -> None:
    """update changes active field and returns the updated row."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="Active blessing", rotation_order=1, active=True)
    await db_session.commit()

    updated = await repo.update(b.id, _USER_ID, active=False)
    await db_session.commit()

    assert updated is not None
    assert updated.active is False
    assert updated.text == "Active blessing"


@pytest.mark.asyncio
async def test_blessing_update_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """update returns None when the id does not exist."""
    repo = BlessingRepository(db_session)
    result = await repo.update(uuid.uuid4(), _USER_ID, text="x")
    assert result is None


@pytest.mark.asyncio
async def test_blessing_update_returns_none_for_wrong_user(db_session: AsyncSession) -> None:
    """update returns None when the blessing belongs to another user."""
    await _seed_user(db_session, _USER_ID)
    await _seed_user(db_session, _OTHER_USER_ID)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_OTHER_USER_ID, text="Other's blessing", rotation_order=1)
    await db_session.commit()

    result = await repo.update(b.id, _USER_ID, text="Stolen")
    assert result is None


@pytest.mark.asyncio
async def test_blessing_delete(db_session: AsyncSession) -> None:
    """delete removes the row and returns True."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="To delete", rotation_order=1)
    await db_session.commit()

    deleted = await repo.delete(b.id, _USER_ID)
    await db_session.commit()

    assert deleted is True
    assert await repo.get_by_id(b.id) is None


@pytest.mark.asyncio
async def test_blessing_delete_returns_false_for_unknown(db_session: AsyncSession) -> None:
    """delete returns False when the id does not exist."""
    repo = BlessingRepository(db_session)
    result = await repo.delete(uuid.uuid4(), _USER_ID)
    assert result is False


@pytest.mark.asyncio
async def test_blessing_delete_returns_false_for_wrong_user(db_session: AsyncSession) -> None:
    """delete returns False when the blessing belongs to another user."""
    await _seed_user(db_session, _USER_ID)
    await _seed_user(db_session, _OTHER_USER_ID)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_OTHER_USER_ID, text="Other's blessing", rotation_order=1)
    await db_session.commit()

    result = await repo.delete(b.id, _USER_ID)
    assert result is False


@pytest.mark.asyncio
async def test_blessing_reorder(db_session: AsyncSession) -> None:
    """reorder assigns rotation_order 1..N in the supplied order."""
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b1 = await repo.create(user_id=_USER_ID, text="A", rotation_order=1)
    b2 = await repo.create(user_id=_USER_ID, text="B", rotation_order=2)
    b3 = await repo.create(user_id=_USER_ID, text="C", rotation_order=3)
    await db_session.commit()

    # Reverse the order
    result = await repo.reorder([b3.id, b1.id, b2.id], _USER_ID)
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
    await _seed_user(db_session)
    repo = BlessingRepository(db_session)

    b = await repo.create(user_id=_USER_ID, text="A", rotation_order=1)
    await db_session.commit()

    with pytest.raises(KeyError):
        await repo.reorder([b.id, uuid.uuid4()], _USER_ID)


@pytest.mark.asyncio
async def test_blessing_reorder_raises_for_wrong_user(db_session: AsyncSession) -> None:
    """reorder raises PermissionError if any blessing belongs to another user."""
    await _seed_user(db_session, _USER_ID)
    await _seed_user(db_session, _OTHER_USER_ID)
    repo = BlessingRepository(db_session)

    b_mine = await repo.create(user_id=_USER_ID, text="Mine", rotation_order=1)
    b_other = await repo.create(user_id=_OTHER_USER_ID, text="Other", rotation_order=1)
    await db_session.commit()

    with pytest.raises(PermissionError):
        await repo.reorder([b_mine.id, b_other.id], _USER_ID)
