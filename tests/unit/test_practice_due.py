"""Unit tests for PracticeService.due_now — frozen-clock evaluation (AC-1).

Covers: fixed_times match/no-match, every_n_hours phase math via anchor_hour,
anchor_minute gating, start/end date gating, inactive practices skipped.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.models.practice import Practice
from bot.repositories.practice_repository import PracticeRepository
from bot.services.practice_service import PracticeService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_practice(
    *,
    content_type: str = "question",
    periodicity_type: str = "fixed_times",
    schedule_times: list[str] | None = None,
    interval_hours: int | None = None,
    anchor_hour: int = 0,
    anchor_minute: int = 0,
    active: bool = True,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "test practice"
    p.content_type = content_type
    p.periodicity_type = periodicity_type
    p.schedule_times = schedule_times
    p.interval_hours = interval_hours
    p.anchor_hour = anchor_hour
    p.anchor_minute = anchor_minute
    p.active = active
    p.start_date = start_date
    p.end_date = end_date
    p.sort_order = 0
    p.media_asset = None
    p.media_asset_id = None
    return p


_USER_ID = 123456789


def make_service(practices: list[Practice]) -> PracticeService:
    repo = MagicMock(spec=PracticeRepository)
    repo.get_active_practices = AsyncMock(return_value=[p for p in practices if p.active])
    return PracticeService(repo)


def dt(hour: int, minute: int = 0, day: int = 10) -> datetime:
    """Return a naive datetime for 2026-06-<day> HH:MM."""
    return datetime(2026, 6, day, hour, minute)


# ---------------------------------------------------------------------------
# fixed_times
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixed_times_match() -> None:
    p = make_practice(periodicity_type="fixed_times", schedule_times=["08:00"])
    svc = make_service([p])
    due = await svc.due_now(_USER_ID, dt(8, 0))
    assert p in due


@pytest.mark.asyncio
async def test_fixed_times_no_match_wrong_hour() -> None:
    p = make_practice(periodicity_type="fixed_times", schedule_times=["08:00"])
    svc = make_service([p])
    due = await svc.due_now(_USER_ID, dt(9, 0))
    assert p not in due


@pytest.mark.asyncio
async def test_fixed_times_no_match_wrong_minute() -> None:
    p = make_practice(periodicity_type="fixed_times", schedule_times=["08:00"])
    svc = make_service([p])
    due = await svc.due_now(_USER_ID, dt(8, 1))
    assert p not in due


@pytest.mark.asyncio
async def test_fixed_times_multiple_slots_match() -> None:
    p = make_practice(periodicity_type="fixed_times", schedule_times=["08:00", "20:00"])
    svc = make_service([p])
    assert p in await svc.due_now(_USER_ID, dt(8, 0))
    assert p in await svc.due_now(_USER_ID, dt(20, 0))
    assert p not in await svc.due_now(_USER_ID, dt(12, 0))


@pytest.mark.asyncio
async def test_fixed_times_empty_schedule() -> None:
    p = make_practice(periodicity_type="fixed_times", schedule_times=[])
    svc = make_service([p])
    due = await svc.due_now(_USER_ID, dt(8, 0))
    assert p not in due


# ---------------------------------------------------------------------------
# every_n_hours phase math
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hourly_anchor_hour_0_fires_every_hour() -> None:
    """interval_hours=1, anchor_hour=0 → fires at :00 every hour."""
    p = make_practice(
        periodicity_type="every_n_hours", interval_hours=1, anchor_hour=0, anchor_minute=0
    )
    svc = make_service([p])
    for hour in range(0, 24):
        result = await svc.due_now(_USER_ID, dt(hour, 0))
        assert p in result, f"Expected due at {hour:02d}:00"


@pytest.mark.asyncio
async def test_hourly_anchor_hour_0_not_due_at_nonzero_minute() -> None:
    p = make_practice(
        periodicity_type="every_n_hours", interval_hours=1, anchor_hour=0, anchor_minute=0
    )
    svc = make_service([p])
    assert p not in await svc.due_now(_USER_ID, dt(8, 30))


@pytest.mark.asyncio
async def test_every_4h_anchor_hour_6_fires_at_correct_hours() -> None:
    """interval_hours=4, anchor_hour=6 → due at 02/06/10/14/18/22 local."""
    p = make_practice(
        periodicity_type="every_n_hours", interval_hours=4, anchor_hour=6, anchor_minute=0
    )
    svc = make_service([p])
    # 6 % 4 == 2, so due when hour % 4 == 2: 02, 06, 10, 14, 18, 22
    due_hours = {2, 6, 10, 14, 18, 22}
    not_due_hours = set(range(24)) - due_hours
    for hour in due_hours:
        assert p in await svc.due_now(_USER_ID, dt(hour, 0)), f"Expected due at {hour:02d}:00"
    for hour in not_due_hours:
        assert p not in await svc.due_now(_USER_ID, dt(hour, 0)), (
            f"Expected NOT due at {hour:02d}:00"
        )


@pytest.mark.asyncio
async def test_every_4h_anchor_minute_gating() -> None:
    """anchor_minute=30 → only fires at HH:30, not HH:00."""
    p = make_practice(
        periodicity_type="every_n_hours", interval_hours=4, anchor_hour=6, anchor_minute=30
    )
    svc = make_service([p])
    assert p not in await svc.due_now(_USER_ID, dt(6, 0))
    assert p in await svc.due_now(_USER_ID, dt(6, 30))
    assert p not in await svc.due_now(_USER_ID, dt(6, 15))


@pytest.mark.asyncio
async def test_every_n_hours_zero_interval_not_due() -> None:
    """interval_hours=0 must never fire (guard against division by zero)."""
    p = make_practice(periodicity_type="every_n_hours", interval_hours=0, anchor_hour=0)
    svc = make_service([p])
    assert p not in await svc.due_now(_USER_ID, dt(8, 0))


# ---------------------------------------------------------------------------
# Date range gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_date_gating_before_start() -> None:
    """Practice is not due before its start_date."""
    p = make_practice(
        periodicity_type="fixed_times",
        schedule_times=["08:00"],
        start_date=datetime(2026, 6, 15, 0, 0),
    )
    svc = make_service([p])
    # 2026-06-10 is before start_date 2026-06-15
    assert p not in await svc.due_now(_USER_ID, dt(8, 0, day=10))


@pytest.mark.asyncio
async def test_start_date_gating_on_start_date() -> None:
    p = make_practice(
        periodicity_type="fixed_times",
        schedule_times=["08:00"],
        start_date=datetime(2026, 6, 10, 0, 0),
    )
    svc = make_service([p])
    assert p in await svc.due_now(_USER_ID, dt(8, 0, day=10))


@pytest.mark.asyncio
async def test_end_date_gating_after_end() -> None:
    """Practice is not due after its end_date."""
    p = make_practice(
        periodicity_type="fixed_times",
        schedule_times=["08:00"],
        end_date=datetime(2026, 6, 9, 0, 0),
    )
    svc = make_service([p])
    assert p not in await svc.due_now(_USER_ID, dt(8, 0, day=10))


@pytest.mark.asyncio
async def test_end_date_gating_on_end_date() -> None:
    p = make_practice(
        periodicity_type="fixed_times",
        schedule_times=["08:00"],
        end_date=datetime(2026, 6, 10, 0, 0),
    )
    svc = make_service([p])
    assert p in await svc.due_now(_USER_ID, dt(8, 0, day=10))


# ---------------------------------------------------------------------------
# Inactive practices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inactive_practice_not_returned() -> None:
    """Inactive practices are filtered out by the repository (active=False row not returned)."""
    active = make_practice(periodicity_type="fixed_times", schedule_times=["08:00"], active=True)
    inactive = make_practice(periodicity_type="fixed_times", schedule_times=["08:00"], active=False)
    svc = make_service([active, inactive])
    due = await svc.due_now(_USER_ID, dt(8, 0))
    assert active in due
    assert inactive not in due
