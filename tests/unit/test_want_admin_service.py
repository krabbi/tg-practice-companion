"""Unit tests for WantAdminService (Stage 2 web admin B6).

Covers create, update, delete transaction handling using AsyncMock.
"""

import uuid
from unittest.mock import AsyncMock

from bot.models.lists import WantListItem
from bot.services.want_admin_service import WantAdminService


def _make_service() -> tuple[WantAdminService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    repo = AsyncMock()
    service = WantAdminService(session, repo)
    return service, session, repo


_USER_ID = 123


def _make_item(user_id: int = _USER_ID, text: str = "Test want") -> WantListItem:
    item = WantListItem()
    item.id = uuid.uuid4()
    item.user_id = user_id
    item.text = text
    item.done = False
    return item


async def test_list_for_user_delegates_to_repo() -> None:
    """list_for_user returns whatever the repo returns."""
    service, _session, repo = _make_service()
    expected = [_make_item(), _make_item()]
    repo.list_for_user.return_value = expected

    result = await service.list_for_user(123)

    assert result == expected
    repo.list_for_user.assert_awaited_once_with(123)


async def test_create_commits_and_returns_item() -> None:
    """create commits and returns the new item."""
    service, session, repo = _make_service()
    item = _make_item()
    repo.create.return_value = item

    result = await service.create(user_id=123, text="Buy flowers")

    repo.create.assert_awaited_once_with(user_id=123, text="Buy flowers")
    session.commit.assert_awaited_once()
    assert result is item


async def test_update_found_commits_and_returns() -> None:
    """update commits and returns the updated item when found."""
    service, session, repo = _make_service()
    item = _make_item()
    repo.update.return_value = item

    result = await service.update(item.id, _USER_ID, text="Updated text", done=True)

    repo.update.assert_awaited_once_with(item.id, _USER_ID, text="Updated text", done=True)
    session.commit.assert_awaited_once()
    assert result is item


async def test_update_not_found_returns_none_without_commit() -> None:
    """update returns None and does not commit when repo returns None."""
    service, session, repo = _make_service()
    repo.update.return_value = None

    result = await service.update(uuid.uuid4(), _USER_ID, text="x")

    assert result is None
    session.commit.assert_not_awaited()


async def test_delete_found_commits_and_returns_true() -> None:
    """delete commits and returns True when the item exists."""
    service, session, repo = _make_service()
    repo.delete.return_value = True

    result = await service.delete(uuid.uuid4(), _USER_ID)

    assert result is True
    session.commit.assert_awaited_once()


async def test_delete_not_found_returns_false_without_commit() -> None:
    """delete returns False and does not commit when the item does not exist."""
    service, session, repo = _make_service()
    repo.delete.return_value = False

    result = await service.delete(uuid.uuid4(), _USER_ID)

    assert result is False
    session.commit.assert_not_awaited()
