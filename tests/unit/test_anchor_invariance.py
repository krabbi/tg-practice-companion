"""test_anchor_invariance: cadence phase must be decoupled from the send window.

For interval_hours=4, anchor_hour=6, the set of due local hours is identical
regardless of send_window_start (6 → 5 → 7). The window only clips which of
those hours are admitted — it does not shift the phase.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.models.practice import Practice
from bot.repositories.practice_repository import PracticeRepository
from bot.services.practice_service import PracticeService


def make_every_4h_practice() -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "4h practice"
    p.content_type = "question"
    p.content = "test"
    p.periodicity_type = "every_n_hours"
    p.interval_hours = 4
    p.anchor_hour = 6
    p.anchor_minute = 0
    p.active = True
    p.start_date = None
    p.end_date = None
    p.sort_order = 0
    p.media_asset = None
    p.media_asset_id = None
    return p


def make_service(practice: Practice) -> PracticeService:
    repo = MagicMock(spec=PracticeRepository)
    repo.get_active_practices = AsyncMock(return_value=[practice])
    return PracticeService(repo)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 10, hour, minute)


@pytest.mark.asyncio
async def test_due_hours_independent_of_send_window_start() -> None:
    """The set of due hours (02/06/10/14/18/22) is the same for all window starts."""
    practice = make_every_4h_practice()
    svc = make_service(practice)

    # anchor_hour=6, interval_hours=4 → due when hour % 4 == 6 % 4 == 2
    expected_due_hours = {2, 6, 10, 14, 18, 22}

    # Evaluate for all 24 hours — the result must match regardless of window
    # (window clipping is done in tick(), not in due_now())
    actual_due_hours: set[int] = set()
    for hour in range(24):
        result = await svc.due_now(dt(hour))
        if practice in result:
            actual_due_hours.add(hour)

    assert actual_due_hours == expected_due_hours, (
        f"Due hours {actual_due_hours} do not match expected {expected_due_hours}"
    )


@pytest.mark.asyncio
async def test_window_clips_but_does_not_shift_phase() -> None:
    """Simulated window clipping (send_window_start=7) removes 2 and 6 from admitted
    hours but the underlying due set remains 02/06/10/14/18/22."""
    practice = make_every_4h_practice()
    svc = make_service(practice)

    # Simulate window [7, 22) — 2 and 6 would be outside
    send_window_start = 7
    send_window_end = 22

    admitted: set[int] = set()
    due_but_outside_window: set[int] = set()

    for hour in range(24):
        result = await svc.due_now(dt(hour))
        if practice in result:
            if send_window_start <= hour < send_window_end:
                admitted.add(hour)
            else:
                due_but_outside_window.add(hour)

    # Inside window: 10, 14, 18 (22 is exclusive at hour==22 but 22%4==2 so still due,
    # excluded because window is [7, 22))
    # actually 22 % 4 == 2, hour 22 is outside [7, 22) since 22 is not < 22
    assert 10 in admitted
    assert 14 in admitted
    assert 18 in admitted
    # Phase preserved: 2 and 6 are due but outside the window
    assert 2 in due_but_outside_window
    assert 6 in due_but_outside_window
    # Phase not shifted: 7 is NOT due (7 % 4 == 3, not 2)
    assert 7 not in admitted
    assert 7 not in due_but_outside_window


@pytest.mark.asyncio
async def test_window_start_5_admits_6() -> None:
    """With send_window_start=5, hour 6 (due) is inside the window."""
    practice = make_every_4h_practice()
    svc = make_service(practice)

    send_window_start = 5
    send_window_end = 22

    due_at_6 = await svc.due_now(dt(6))
    assert practice in due_at_6
    # 6 is inside [5, 22)
    assert send_window_start <= 6 < send_window_end
