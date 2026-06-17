"""Unit tests for BlessingAdminService (Stage 2 web admin B6).

Covers create, update, delete, reorder transaction handling using AsyncMock.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from bot.models.morning import MorningBlessing
from bot.services.blessing_admin_service import BlessingAdminService


def _make_service() -> tuple[BlessingAdminService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    repo = AsyncMock()
    service = BlessingAdminService(session, repo)
    return service, session, repo


def _make_blessing(text: str = "Test blessing", rotation_order: int = 1) -> MorningBlessing:
    b = MorningBlessing()
    b.id = uuid.uuid4()
    b.text = text
    b.rotation_order = rotation_order
    b.active = True
    return b


async def test_list_all_delegates_to_repo() -> None:
    """list_all returns whatever the repo returns."""
    service, _session, repo = _make_service()
    expected = [_make_blessing(rotation_order=1), _make_blessing(rotation_order=2)]
    repo.list_all.return_value = expected

    result = await service.list_all()

    assert result == expected
    repo.list_all.assert_awaited_once()


async def test_create_appends_to_end_and_commits() -> None:
    """create computes next rotation_order from existing rows and commits."""
    service, session, repo = _make_service()
    existing = [_make_blessing(rotation_order=1), _make_blessing(rotation_order=2)]
    repo.list_all.return_value = existing
    created = _make_blessing(rotation_order=3)
    repo.create.return_value = created

    result = await service.create(text="New blessing")

    repo.create.assert_awaited_once_with(text="New blessing", rotation_order=3, active=True)
    session.commit.assert_awaited_once()
    assert result is created


async def test_create_with_no_existing_uses_order_one() -> None:
    """create assigns rotation_order=1 when no blessings exist yet."""
    service, session, repo = _make_service()
    repo.list_all.return_value = []
    created = _make_blessing(rotation_order=1)
    repo.create.return_value = created

    result = await service.create(text="First blessing")

    repo.create.assert_awaited_once_with(text="First blessing", rotation_order=1, active=True)
    session.commit.assert_awaited_once()
    assert result is created


async def test_create_passes_active_flag() -> None:
    """create forwards the active parameter to the repo."""
    service, session, repo = _make_service()
    repo.list_all.return_value = []
    repo.create.return_value = _make_blessing()

    await service.create(text="Draft", active=False)

    repo.create.assert_awaited_once_with(text="Draft", rotation_order=1, active=False)


async def test_update_found_commits_and_returns() -> None:
    """update commits and returns the updated blessing when found."""
    service, session, repo = _make_service()
    blessing = _make_blessing()
    repo.update.return_value = blessing

    result = await service.update(blessing.id, text="New text", active=False)

    repo.update.assert_awaited_once_with(blessing.id, text="New text", active=False)
    session.commit.assert_awaited_once()
    assert result is blessing


async def test_update_not_found_returns_none_without_commit() -> None:
    """update returns None and does not commit when repo returns None."""
    service, session, repo = _make_service()
    repo.update.return_value = None

    result = await service.update(uuid.uuid4(), text="x")

    assert result is None
    session.commit.assert_not_awaited()


async def test_delete_found_commits_and_returns_true() -> None:
    """delete commits and returns True when the blessing exists."""
    service, session, repo = _make_service()
    repo.delete.return_value = True

    result = await service.delete(uuid.uuid4())

    assert result is True
    session.commit.assert_awaited_once()


async def test_delete_not_found_returns_false_without_commit() -> None:
    """delete returns False and does not commit when the blessing does not exist."""
    service, session, repo = _make_service()
    repo.delete.return_value = False

    result = await service.delete(uuid.uuid4())

    assert result is False
    session.commit.assert_not_awaited()


async def test_reorder_validates_and_commits() -> None:
    """reorder delegates to repo and commits when input IDs match exactly."""
    service, session, repo = _make_service()
    b1 = _make_blessing(rotation_order=1)
    b2 = _make_blessing(rotation_order=2)
    repo.list_all.return_value = [b1, b2]
    repo.reorder.return_value = [b2, b1]

    result = await service.reorder([b2.id, b1.id])

    repo.reorder.assert_awaited_once_with([b2.id, b1.id])
    session.commit.assert_awaited_once()
    assert result == [b2, b1]


async def test_reorder_raises_for_unknown_ids() -> None:
    """reorder raises ValueError when the input contains IDs not in the DB."""
    service, _session, repo = _make_service()
    b1 = _make_blessing(rotation_order=1)
    repo.list_all.return_value = [b1]

    with pytest.raises(ValueError, match="Unknown blessing IDs"):
        await service.reorder([b1.id, uuid.uuid4()])


async def test_reorder_raises_for_missing_ids() -> None:
    """reorder raises ValueError when existing IDs are omitted from the input."""
    service, _session, repo = _make_service()
    b1 = _make_blessing(rotation_order=1)
    b2 = _make_blessing(rotation_order=2)
    repo.list_all.return_value = [b1, b2]

    with pytest.raises(ValueError, match="Missing blessing IDs"):
        await service.reorder([b1.id])
