"""Tests for BlessingService rotation and compose() ordering (AC-3).

Verifies that:
- BlessingService.for_date() cycles through morning_blessings in rotation_order
  on consecutive calendar days and wraps after the last blessing.
- compose() sorts practices by sort_order ascending.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.models.morning import MorningBlessing
from bot.models.practice import Practice
from bot.repositories.blessing_repository import BlessingRepository
from bot.scheduler import compose
from bot.services.blessing_service import BlessingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_blessing(text: str, rotation_order: int) -> MorningBlessing:
    b = MorningBlessing()
    b.id = uuid.uuid4()
    b.text = text
    b.rotation_order = rotation_order
    b.active = True
    return b


def make_practice(sort_order: int, name: str = "test") -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = name
    p.content_type = "text"
    p.content = f"content of {name}"
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["06:00"]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.sort_order = sort_order
    p.media_asset_id = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    return p


# ---------------------------------------------------------------------------
# BlessingService.for_date — no active blessings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_for_date_returns_none_when_no_blessings() -> None:
    """Returns None when no active blessings exist."""
    mock_repo = MagicMock(spec=BlessingRepository)
    mock_repo.get_active_ordered = AsyncMock(return_value=[])
    svc = BlessingService(mock_repo)

    result = await svc.for_date(date(2026, 6, 10))
    assert result is None


# ---------------------------------------------------------------------------
# BlessingService.for_date — rotation across consecutive days (AC-3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_for_date_consecutive_days_cycle_rotation_order() -> None:
    """Consecutive calendar days cycle through blessings in rotation_order sequence."""
    blessings = [
        make_blessing("Blessing A", 1),
        make_blessing("Blessing B", 2),
        make_blessing("Blessing C", 3),
    ]
    mock_repo = MagicMock(spec=BlessingRepository)
    mock_repo.get_active_ordered = AsyncMock(return_value=blessings)
    svc = BlessingService(mock_repo)

    # Collect 4 consecutive days
    results = [await svc.for_date(date(2026, 6, 10 + i)) for i in range(4)]

    texts = [r.text for r in results]
    # First three days must all be different blessings
    assert len(set(texts[:3])) == 3, "Three consecutive days should yield three distinct blessings"
    # Fourth day wraps back to the same as the first
    assert texts[3] == texts[0], "Fourth day should wrap to the first blessing in the rotation"


@pytest.mark.asyncio
async def test_for_date_wraps_after_last_blessing() -> None:
    """After exhausting the list the rotation wraps to blessing with lowest rotation_order."""
    blessings = [make_blessing("X", 1), make_blessing("Y", 2)]
    mock_repo = MagicMock(spec=BlessingRepository)
    mock_repo.get_active_ordered = AsyncMock(return_value=blessings)
    svc = BlessingService(mock_repo)

    # Collect enough days to see the wrap
    texts = [await svc.for_date(date(2026, 6, 10 + i)) for i in range(4)]
    texts = [b.text for b in texts]
    # Pattern must alternate: (X,Y) or (Y,X) repeating — exactly 2 distinct values
    assert len(set(texts)) == 2
    # Day 2 wraps to day 0
    assert texts[2] == texts[0]
    assert texts[3] == texts[1]


@pytest.mark.asyncio
async def test_for_date_single_blessing_always_returns_same() -> None:
    """A single active blessing is returned every day (trivial rotation)."""
    only = make_blessing("The one blessing", 1)
    mock_repo = MagicMock(spec=BlessingRepository)
    mock_repo.get_active_ordered = AsyncMock(return_value=[only])
    svc = BlessingService(mock_repo)

    for day in range(1, 5):
        result = await svc.for_date(date(2026, 6, 10 + day))
        assert result is not None
        assert result.text == "The one blessing"


@pytest.mark.asyncio
async def test_for_date_same_date_idempotent() -> None:
    """Calling for_date() twice with the same date returns the same blessing."""
    blessings = [make_blessing("M", 1), make_blessing("N", 2)]
    mock_repo = MagicMock(spec=BlessingRepository)
    mock_repo.get_active_ordered = AsyncMock(return_value=blessings)
    svc = BlessingService(mock_repo)

    d = date(2026, 6, 10)
    first = await svc.for_date(d)
    second = await svc.for_date(d)
    assert first is not None and second is not None
    assert first.text == second.text


# ---------------------------------------------------------------------------
# compose() — sort_order based ordering
# ---------------------------------------------------------------------------


def test_compose_sorts_by_sort_order_ascending() -> None:
    """compose() returns practices ordered by sort_order ascending."""
    p1 = make_practice(sort_order=100, name="hourly question")
    p2 = make_practice(sort_order=30, name="morning practice")
    p3 = make_practice(sort_order=40, name="motivational image")

    result = compose([p1, p2, p3])
    assert [p.sort_order for p in result] == [30, 40, 100]


def test_compose_empty_list() -> None:
    """compose() on an empty list returns an empty list."""
    assert compose([]) == []


def test_compose_single_item() -> None:
    """compose() on a single practice returns it unchanged."""
    p = make_practice(sort_order=10)
    assert compose([p]) == [p]


def test_compose_preserves_all_practices() -> None:
    """compose() never drops or duplicates practices."""
    practices = [make_practice(i * 10) for i in range(5)]
    result = compose(practices)
    assert len(result) == 5
    assert {p.id for p in result} == {p.id for p in practices}
