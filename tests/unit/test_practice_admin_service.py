"""Unit tests for PracticeAdminService (Stage 2 web admin CRUD, B3 / #68).

Covers list/get delegation, create/update/delete transaction handling, and the
schedule-validation branches (anchor-window admissibility, fixed-times HH:MM).
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from bot.models.practice import Practice
from bot.services.practice_admin_service import (
    PracticeAdminService,
    PracticeValidationError,
)


def _make_service() -> tuple[PracticeAdminService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    repo = AsyncMock()
    service = PracticeAdminService(session, repo, send_window_start=6, send_window_end=22)
    return service, session, repo


_USER_ID = 123456789


def _make_practice(**overrides) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.user_id = _USER_ID
    p.name = "existing"
    p.content_type = "text"
    p.content = "hello"
    p.media_asset_id = None
    p.periodicity_type = "fixed_times"
    p.interval_hours = None
    p.schedule_times = ["10:00"]
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.active = True
    p.start_date = None
    p.end_date = None
    p.sort_order = 0
    for key, value in overrides.items():
        setattr(p, key, value)
    return p


_CREATE_KW = dict(
    user_id=_USER_ID,
    name="daily text",
    content_type="text",
    content="hi",
    media_asset_id=None,
    periodicity_type="fixed_times",
    interval_hours=None,
    schedule_times=["10:00"],
    anchor_hour=0,
    anchor_minute=0,
    active=True,
    start_date=None,
    end_date=None,
    sort_order=0,
)


async def test_list_all_delegates_to_repo():
    service, _session, repo = _make_service()
    expected = [_make_practice(), _make_practice()]
    repo.list_all.return_value = expected

    result = await service.list_all(_USER_ID, active=True)

    assert result == expected
    repo.list_all.assert_awaited_once_with(_USER_ID, True)


async def test_get_delegates_to_repo():
    service, _session, repo = _make_service()
    practice = _make_practice()
    repo.get_by_id.return_value = practice

    result = await service.get(practice.id, _USER_ID)

    assert result is practice
    repo.get_by_id.assert_awaited_once_with(practice.id)


async def test_get_returns_none_for_wrong_user():
    """get returns None when practice belongs to another user."""
    service, _session, repo = _make_service()
    practice = _make_practice(user_id=999)
    repo.get_by_id.return_value = practice

    result = await service.get(practice.id, _USER_ID)

    assert result is None


async def test_create_persists_and_commits():
    service, session, repo = _make_service()

    practice = await service.create(**_CREATE_KW)

    assert practice.name == "daily text"
    repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_create_every_n_hours_requires_interval_hours():
    service, _session, repo = _make_service()
    kw = {**_CREATE_KW, "periodicity_type": "every_n_hours", "interval_hours": None}

    with pytest.raises(PracticeValidationError, match="interval_hours is required"):
        await service.create(**kw)

    repo.save.assert_not_awaited()


async def test_create_interval_below_one_rejected():
    service, _session, _repo = _make_service()
    kw = {**_CREATE_KW, "periodicity_type": "every_n_hours", "interval_hours": 0}

    with pytest.raises(PracticeValidationError, match="must be >= 1"):
        await service.create(**kw)


async def test_create_no_slot_in_send_window_rejected():
    service, _session, _repo = _make_service()
    # interval 24h anchored at hour 0 → only slot is 00:00, outside [06:00, 22:00).
    kw = {
        **_CREATE_KW,
        "periodicity_type": "every_n_hours",
        "interval_hours": 24,
        "anchor_hour": 0,
    }

    with pytest.raises(PracticeValidationError, match="never fire"):
        await service.create(**kw)


async def test_create_every_n_hours_valid_window_passes():
    service, session, repo = _make_service()
    kw = {
        **_CREATE_KW,
        "periodicity_type": "every_n_hours",
        "interval_hours": 3,
        "anchor_hour": 6,
    }

    await service.create(**kw)

    repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_create_fixed_times_bad_hhmm_rejected():
    service, _session, _repo = _make_service()
    kw = {**_CREATE_KW, "periodicity_type": "fixed_times", "schedule_times": ["25:00"]}

    with pytest.raises(PracticeValidationError, match="Invalid HH:MM"):
        await service.create(**kw)


async def test_update_applies_changes_and_commits():
    service, session, repo = _make_service()
    practice = _make_practice()
    repo.get_by_id.return_value = practice

    result = await service.update(practice.id, _USER_ID, {"content": "updated"})

    assert result is practice
    assert practice.content == "updated"
    repo.save.assert_awaited_once_with(practice)
    session.commit.assert_awaited_once()


async def test_update_missing_returns_none():
    service, session, repo = _make_service()
    repo.get_by_id.return_value = None

    result = await service.update(uuid.uuid4(), _USER_ID, {"content": "x"})

    assert result is None
    repo.save.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_update_wrong_user_returns_none():
    """update returns None when practice belongs to another user."""
    service, session, repo = _make_service()
    practice = _make_practice(user_id=999)
    repo.get_by_id.return_value = practice

    result = await service.update(practice.id, _USER_ID, {"content": "x"})

    assert result is None
    repo.save.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_update_revalidates_schedule():
    service, _session, repo = _make_service()
    practice = _make_practice()
    repo.get_by_id.return_value = practice

    with pytest.raises(PracticeValidationError, match="Invalid HH:MM"):
        await service.update(practice.id, _USER_ID, {"schedule_times": ["99:99"]})


async def test_delete_found_commits_and_returns_true():
    service, session, repo = _make_service()
    repo.delete.return_value = True

    result = await service.delete(uuid.uuid4(), _USER_ID)

    assert result is True
    session.commit.assert_awaited_once()


async def test_delete_missing_returns_false_without_commit():
    service, session, repo = _make_service()
    repo.delete.return_value = False

    result = await service.delete(uuid.uuid4(), _USER_ID)

    assert result is False
    session.commit.assert_not_awaited()
