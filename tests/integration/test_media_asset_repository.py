"""Integration tests for MediaAssetRepository (B4 / #69).

Exercises create (flush+refresh), list_all with/without kind filter, get
(found/none/wrong-user), and delete (found/not-found/wrong-user) against the SQLite :memory: session.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import MediaAsset
from bot.models.user import User
from bot.repositories.media_asset_repository import MediaAssetRepository

TEST_USER_ID = 123456789
OTHER_USER_ID = 999888777


async def _seed_user(session: AsyncSession, telegram_id: int) -> None:
    user = User(telegram_id=telegram_id, language="ru")
    session.add(user)
    await session.flush()


def _make_asset(kind: str = "image", user_id: int = TEST_USER_ID) -> MediaAsset:
    return MediaAsset(
        id=uuid.uuid4(),
        kind=kind,
        storage_path=f"/data/media/{uuid.uuid4()}.bin",
        telegram_file_id=None,
        mime="application/octet-stream",
        user_id=user_id,
    )


async def test_create_flushes_and_returns_row(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    asset = _make_asset()

    created = await repo.create(asset)

    assert created.id == asset.id
    fetched = await repo.get(asset.id, TEST_USER_ID)
    assert fetched is not None
    assert fetched.id == asset.id


async def test_list_all_returns_every_row(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    await repo.create(_make_asset("image"))
    await repo.create(_make_asset("audio"))

    result = await repo.list_all(TEST_USER_ID)

    assert len(result) == 2


async def test_list_all_filters_by_kind(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    await repo.create(_make_asset("image"))
    await repo.create(_make_asset("audio"))

    images = await repo.list_all(TEST_USER_ID, kind="image")

    assert len(images) == 1
    assert images[0].kind == "image"


async def test_list_all_user_isolation(db_session: AsyncSession):
    """list_all returns only assets for the given user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = MediaAssetRepository(db_session)

    await repo.create(_make_asset("image", TEST_USER_ID))
    await repo.create(_make_asset("image", OTHER_USER_ID))

    result = await repo.list_all(TEST_USER_ID)

    assert len(result) == 1
    assert result[0].user_id == TEST_USER_ID


async def test_get_returns_none_for_unknown_id(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)

    assert await repo.get(uuid.uuid4(), TEST_USER_ID) is None


async def test_get_returns_none_for_wrong_user(db_session: AsyncSession):
    """get returns None when the asset belongs to another user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = MediaAssetRepository(db_session)

    asset = await repo.create(_make_asset("image", OTHER_USER_ID))

    assert await repo.get(asset.id, TEST_USER_ID) is None


async def test_delete_found_returns_true(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    asset = await repo.create(_make_asset())

    deleted = await repo.delete(asset.id, TEST_USER_ID)

    assert deleted is True
    assert await repo.get(asset.id, TEST_USER_ID) is None


async def test_delete_missing_returns_false(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)

    assert await repo.delete(uuid.uuid4(), TEST_USER_ID) is False


async def test_delete_wrong_user_returns_false(db_session: AsyncSession):
    """delete returns False when the asset belongs to another user."""
    await _seed_user(db_session, TEST_USER_ID)
    await _seed_user(db_session, OTHER_USER_ID)
    repo = MediaAssetRepository(db_session)

    asset = await repo.create(_make_asset("image", OTHER_USER_ID))

    assert await repo.delete(asset.id, TEST_USER_ID) is False
