"""Integration tests for MediaAssetRepository (B4 / #69).

Exercises create (flush+refresh), list_all with/without kind filter, get
(found/none), and delete (found/not-found) against the SQLite :memory: session.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.practice import MediaAsset
from bot.repositories.media_asset_repository import MediaAssetRepository


def _make_asset(kind: str = "image") -> MediaAsset:
    return MediaAsset(
        id=uuid.uuid4(),
        kind=kind,
        storage_path=f"/data/media/{uuid.uuid4()}.bin",
        telegram_file_id=None,
        mime="application/octet-stream",
    )


async def test_create_flushes_and_returns_row(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    asset = _make_asset()

    created = await repo.create(asset)

    assert created.id == asset.id
    fetched = await repo.get(asset.id)
    assert fetched is not None
    assert fetched.id == asset.id


async def test_list_all_returns_every_row(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    await repo.create(_make_asset("image"))
    await repo.create(_make_asset("audio"))

    result = await repo.list_all()

    assert len(result) == 2


async def test_list_all_filters_by_kind(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    await repo.create(_make_asset("image"))
    await repo.create(_make_asset("audio"))

    images = await repo.list_all(kind="image")

    assert len(images) == 1
    assert images[0].kind == "image"


async def test_get_returns_none_for_unknown_id(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)

    assert await repo.get(uuid.uuid4()) is None


async def test_delete_found_returns_true(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)
    asset = await repo.create(_make_asset())

    deleted = await repo.delete(asset.id)

    assert deleted is True
    assert await repo.get(asset.id) is None


async def test_delete_missing_returns_false(db_session: AsyncSession):
    repo = MediaAssetRepository(db_session)

    assert await repo.delete(uuid.uuid4()) is False
