"""Unit tests for UserRepository (list_all and get_or_create methods)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_list_all_returns_all_users(db_session: AsyncSession) -> None:
    """list_all returns all users ordered by telegram_id."""
    repo = UserRepository(db_session)

    u1 = await repo.get_or_create(telegram_id=111, language="ru")
    u2 = await repo.get_or_create(telegram_id=333, language="en")
    u3 = await repo.get_or_create(telegram_id=222, language="ru")
    await db_session.commit()

    result = await repo.list_all()

    assert len(result) == 3
    assert result[0].telegram_id == u1.telegram_id
    assert result[1].telegram_id == u3.telegram_id
    assert result[2].telegram_id == u2.telegram_id


@pytest.mark.asyncio
async def test_list_all_empty(db_session: AsyncSession) -> None:
    """list_all returns empty list when no users exist."""
    repo = UserRepository(db_session)
    result = await repo.list_all()
    assert result == []


@pytest.mark.asyncio
async def test_get_or_create_creates_new_user(db_session: AsyncSession) -> None:
    """get_or_create creates and flushes a new user when absent."""
    repo = UserRepository(db_session)

    user = await repo.get_or_create(telegram_id=999, language="ru")
    await db_session.commit()

    assert user.telegram_id == 999
    assert user.language == "ru"

    fetched = await repo.get_by_telegram_id(999)
    assert fetched is not None
    assert fetched.telegram_id == 999


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_user(db_session: AsyncSession) -> None:
    """get_or_create returns the existing user without creating a duplicate."""
    repo = UserRepository(db_session)

    first = await repo.get_or_create(telegram_id=777, language="ru")
    await db_session.commit()

    second = await repo.get_or_create(telegram_id=777, language="en")
    await db_session.commit()

    assert first.telegram_id == second.telegram_id
    result = await repo.list_all()
    assert len([u for u in result if u.telegram_id == 777]) == 1
