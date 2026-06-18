"""Unit tests for WantListRepository and GoodDeedRepository (SQLite in-memory).

Tests cover full CRUD round-trips for both repositories.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.want_list_repository import WantListRepository

# ---------------------------------------------------------------------------
# WantListRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_want_list_create_and_get(db_session: AsyncSession) -> None:
    """create() persists an item and get_by_id retrieves it."""
    repo = WantListRepository(db_session)

    item = await repo.create(user_id=111, text="Buy a guitar")
    await db_session.commit()

    fetched = await repo.get_by_id(item.id, 111)
    assert fetched is not None
    assert fetched.id == item.id
    assert fetched.text == "Buy a guitar"
    assert fetched.user_id == 111
    assert fetched.done is False


@pytest.mark.asyncio
async def test_want_list_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a non-existent id."""
    repo = WantListRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4(), 111)
    assert result is None


@pytest.mark.asyncio
async def test_want_list_list_for_user(db_session: AsyncSession) -> None:
    """list_for_user returns all items for the given user, oldest first."""
    repo = WantListRepository(db_session)

    item1 = await repo.create(user_id=222, text="Item A")
    await db_session.commit()
    item2 = await repo.create(user_id=222, text="Item B")
    await db_session.commit()
    # Different user — must not appear
    await repo.create(user_id=999, text="Other user item")
    await db_session.commit()

    items = await repo.list_for_user(222)
    assert len(items) == 2
    assert items[0].id == item1.id
    assert items[1].id == item2.id


@pytest.mark.asyncio
async def test_want_list_list_for_user_empty(db_session: AsyncSession) -> None:
    """list_for_user returns an empty list when the user has no items."""
    repo = WantListRepository(db_session)
    items = await repo.list_for_user(333)
    assert items == []


@pytest.mark.asyncio
async def test_want_list_mark_done(db_session: AsyncSession) -> None:
    """mark_done sets done=True and returns the updated item."""
    repo = WantListRepository(db_session)

    item = await repo.create(user_id=444, text="Learn piano")
    await db_session.commit()
    assert item.done is False

    updated = await repo.mark_done(item.id, 444)
    await db_session.commit()

    assert updated is not None
    assert updated.done is True

    fetched = await repo.get_by_id(item.id, 444)
    assert fetched is not None
    assert fetched.done is True


@pytest.mark.asyncio
async def test_want_list_mark_done_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """mark_done returns None when the item does not exist."""
    repo = WantListRepository(db_session)
    result = await repo.mark_done(uuid.uuid4(), 444)
    assert result is None


@pytest.mark.asyncio
async def test_want_list_delete(db_session: AsyncSession) -> None:
    """delete removes the item and returns True."""
    repo = WantListRepository(db_session)

    item = await repo.create(user_id=555, text="Travel to Japan")
    await db_session.commit()

    deleted = await repo.delete(item.id, 555)
    await db_session.commit()

    assert deleted is True
    assert await repo.get_by_id(item.id, 555) is None


@pytest.mark.asyncio
async def test_want_list_delete_returns_false_for_unknown(db_session: AsyncSession) -> None:
    """delete returns False when the item does not exist."""
    repo = WantListRepository(db_session)
    result = await repo.delete(uuid.uuid4(), 555)
    assert result is False


# ---------------------------------------------------------------------------
# GoodDeedRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_good_deed_create_and_get(db_session: AsyncSession) -> None:
    """create() persists a deed and get_by_id retrieves it."""
    repo = GoodDeedRepository(db_session)
    today = date(2026, 6, 15)

    deed = await repo.create(user_id=111, text="Helped a neighbour", deed_date=today)
    await db_session.commit()

    fetched = await repo.get_by_id(deed.id)
    assert fetched is not None
    assert fetched.id == deed.id
    assert fetched.text == "Helped a neighbour"
    assert fetched.user_id == 111
    assert fetched.deed_date == today


@pytest.mark.asyncio
async def test_good_deed_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a non-existent id."""
    repo = GoodDeedRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_good_deed_list_by_date(db_session: AsyncSession) -> None:
    """list_by_date returns all deeds for the given user and date."""
    repo = GoodDeedRepository(db_session)
    today = date(2026, 6, 15)
    yesterday = date(2026, 6, 14)

    deed1 = await repo.create(user_id=222, text="Deed 1", deed_date=today)
    await db_session.commit()
    deed2 = await repo.create(user_id=222, text="Deed 2", deed_date=today)
    await db_session.commit()
    # Different date — must not appear
    await repo.create(user_id=222, text="Yesterday deed", deed_date=yesterday)
    await db_session.commit()
    # Different user — must not appear
    await repo.create(user_id=999, text="Other user deed", deed_date=today)
    await db_session.commit()

    deeds = await repo.list_by_date(222, today)
    assert len(deeds) == 2
    assert deeds[0].id == deed1.id
    assert deeds[1].id == deed2.id


@pytest.mark.asyncio
async def test_good_deed_list_by_date_empty(db_session: AsyncSession) -> None:
    """list_by_date returns an empty list when no deeds exist for that date."""
    repo = GoodDeedRepository(db_session)
    result = await repo.list_by_date(333, date(2026, 6, 15))
    assert result == []


@pytest.mark.asyncio
async def test_good_deed_delete(db_session: AsyncSession) -> None:
    """delete removes the deed and returns True."""
    repo = GoodDeedRepository(db_session)

    deed = await repo.create(user_id=444, text="Donated to charity", deed_date=date(2026, 6, 15))
    await db_session.commit()

    deleted = await repo.delete(deed.id)
    await db_session.commit()

    assert deleted is True
    assert await repo.get_by_id(deed.id) is None


@pytest.mark.asyncio
async def test_good_deed_delete_returns_false_for_unknown(db_session: AsyncSession) -> None:
    """delete returns False when the deed does not exist."""
    repo = GoodDeedRepository(db_session)
    result = await repo.delete(uuid.uuid4())
    assert result is False
