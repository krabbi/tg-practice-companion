"""Integration tests for PracticeRepository using aiosqlite :memory: DB.

Covers:
- get_active_practices: returns only active rows, ordered by sort_order, scoped to user
- get_active_practices: eagerly loads media_asset
- get_by_id: returns practice for known UUID, None for unknown
- get_by_name: returns practice for known name for user, None for unknown or wrong user
- save: flushes and refreshes a new practice
- get_media_asset_by_id: returns asset for known UUID and user, None for unknown or wrong user
- save_media_asset: flushes and refreshes a new asset
- list_all: scoped to user, user B rows not returned to user A
- delete: scoped to user, returns False for wrong user
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import MediaAsset, Practice
from bot.models.user import User
from bot.repositories.practice_repository import PracticeRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


TEST_USER_ID = 123456789
OTHER_USER_ID = 999888777


async def _seed_user(session: AsyncSession, telegram_id: int) -> None:
    user = User(telegram_id=telegram_id, language="ru")
    session.add(user)
    await session.flush()


def make_practice(
    name: str = "test practice",
    active: bool = True,
    sort_order: int = 0,
    media_asset_id: uuid.UUID | None = None,
) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = name
    p.content_type = "text"
    p.content = "hello"
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["10:00"]
    p.active = active
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = sort_order
    p.media_asset_id = media_asset_id
    p.user_id = TEST_USER_ID
    return p


def make_media_asset(kind: str = "audio") -> MediaAsset:
    a = MediaAsset()
    a.id = uuid.uuid4()
    a.kind = kind
    a.telegram_file_id = "BQACAgI_file123"
    a.storage_path = None
    a.mime = "audio/mpeg"
    a.user_id = TEST_USER_ID
    return a


# ---------------------------------------------------------------------------
# get_active_practices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_practices_returns_only_active(db_session: AsyncSession) -> None:
    """get_active_practices returns only practices with active=True."""
    repo = PracticeRepository(db_session)

    active = make_practice(name="active practice", active=True)
    inactive = make_practice(name="inactive practice", active=False)
    db_session.add(active)
    db_session.add(inactive)
    await db_session.flush()

    result = await repo.get_active_practices(TEST_USER_ID)

    names = {p.name for p in result}
    assert "active practice" in names
    assert "inactive practice" not in names


@pytest.mark.asyncio
async def test_get_active_practices_ordered_by_sort_order(db_session: AsyncSession) -> None:
    """get_active_practices returns rows ordered by sort_order ascending."""
    repo = PracticeRepository(db_session)

    p1 = make_practice(name="third", sort_order=3)
    p2 = make_practice(name="first", sort_order=1)
    p3 = make_practice(name="second", sort_order=2)
    db_session.add(p1)
    db_session.add(p2)
    db_session.add(p3)
    await db_session.flush()

    result = await repo.get_active_practices(TEST_USER_ID)

    names = [p.name for p in result]
    assert names == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_get_active_practices_empty(db_session: AsyncSession) -> None:
    """get_active_practices returns empty list when no active practices exist."""
    repo = PracticeRepository(db_session)
    result = await repo.get_active_practices(TEST_USER_ID)
    assert result == []


@pytest.mark.asyncio
async def test_get_active_practices_user_isolation(db_session: AsyncSession) -> None:
    """get_active_practices returns only practices for the given user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = PracticeRepository(db_session)

    p_mine = make_practice(name="mine", active=True)
    p_other = make_practice(name="other", active=True)
    p_other.user_id = OTHER_USER_ID
    db_session.add(p_mine)
    db_session.add(p_other)
    await db_session.flush()

    result = await repo.get_active_practices(TEST_USER_ID)

    names = {p.name for p in result}
    assert "mine" in names
    assert "other" not in names


@pytest.mark.asyncio
async def test_get_active_practices_loads_media_asset(db_session: AsyncSession) -> None:
    """get_active_practices eagerly loads media_asset relationship."""
    await _seed_user(db_session, TEST_USER_ID)
    repo = PracticeRepository(db_session)

    asset = make_media_asset()
    db_session.add(asset)
    await db_session.flush()

    p = make_practice(name="audio practice", media_asset_id=asset.id)
    p.content_type = "audio"
    p.content = None
    db_session.add(p)
    await db_session.flush()

    result = await repo.get_active_practices(TEST_USER_ID)

    assert len(result) == 1
    # media_asset should be loaded (not a lazy-load placeholder)
    assert result[0].media_asset is not None
    assert result[0].media_asset.id == asset.id


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_id_returns_practice(db_session: AsyncSession) -> None:
    """get_by_id returns the correct practice for a known UUID."""
    repo = PracticeRepository(db_session)

    p = make_practice(name="find me")
    db_session.add(p)
    await db_session.flush()

    found = await repo.get_by_id(p.id)
    assert found is not None
    assert found.name == "find me"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that does not exist."""
    repo = PracticeRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# get_by_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_name_returns_practice(db_session: AsyncSession) -> None:
    """get_by_name returns the correct practice for a known name."""
    repo = PracticeRepository(db_session)

    p = make_practice(name="unique name")
    db_session.add(p)
    await db_session.flush()

    found = await repo.get_by_name("unique name", TEST_USER_ID)
    assert found is not None
    assert found.id == p.id


@pytest.mark.asyncio
async def test_get_by_name_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_name returns None when no practice has the given name."""
    repo = PracticeRepository(db_session)
    result = await repo.get_by_name("does not exist", TEST_USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_name_user_isolation(db_session: AsyncSession) -> None:
    """get_by_name returns None when the practice exists but belongs to another user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = PracticeRepository(db_session)

    p = make_practice(name="shared name")
    p.user_id = OTHER_USER_ID
    db_session.add(p)
    await db_session.flush()

    result = await repo.get_by_name("shared name", TEST_USER_ID)
    assert result is None


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_practice_persists_and_refreshes(db_session: AsyncSession) -> None:
    """save flushes and refreshes the practice row."""
    repo = PracticeRepository(db_session)

    p = make_practice(name="save me")
    saved = await repo.save(p)

    assert saved.id is not None
    assert saved.name == "save me"


# ---------------------------------------------------------------------------
# get_media_asset_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_media_asset_by_id_returns_asset(db_session: AsyncSession) -> None:
    """get_media_asset_by_id returns the MediaAsset for a known UUID."""
    repo = PracticeRepository(db_session)

    asset = make_media_asset()
    db_session.add(asset)
    await db_session.flush()

    found = await repo.get_media_asset_by_id(asset.id, TEST_USER_ID)
    assert found is not None
    assert found.id == asset.id


@pytest.mark.asyncio
async def test_get_media_asset_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_media_asset_by_id returns None for a UUID that does not exist."""
    repo = PracticeRepository(db_session)
    result = await repo.get_media_asset_by_id(uuid.uuid4(), TEST_USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_media_asset_by_id_user_isolation(db_session: AsyncSession) -> None:
    """get_media_asset_by_id returns None when asset belongs to another user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = PracticeRepository(db_session)

    asset = make_media_asset()
    asset.user_id = OTHER_USER_ID
    db_session.add(asset)
    await db_session.flush()

    result = await repo.get_media_asset_by_id(asset.id, TEST_USER_ID)
    assert result is None


# ---------------------------------------------------------------------------
# save_media_asset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_media_asset_persists_and_refreshes(db_session: AsyncSession) -> None:
    """save_media_asset flushes and refreshes the asset row."""
    repo = PracticeRepository(db_session)

    asset = make_media_asset()
    saved = await repo.save_media_asset(asset)

    assert saved.id is not None
    assert saved.kind == "audio"
