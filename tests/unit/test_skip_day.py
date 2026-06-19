"""Unit tests for the skip-day feature (AC-5).

After /skip_day, ticks for the rest of the local day send nothing.
Next local day resumes.
"""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import Config
from bot.models.practice import Practice
from bot.models.user import User
from bot.repositories.user_repository import UserRepository
from bot.scheduler import tick
from bot.services.skip_day_service import SkipDayService


def make_practice() -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "skip test"
    p.content_type = "text"
    p.content = "hello"
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["10:00"]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = 0
    p.media_asset = None
    p.media_asset_id = None
    return p


def make_user(skip_until: date | None = None) -> User:
    u = User()
    u.telegram_id = 123456789
    u.timezone = "UTC"
    u.skip_until = skip_until
    u.tz_changed_at = None
    u.language = "ru"
    return u


def make_config() -> Config:
    return Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "allowed_user_ids": "123456789",
            "send_window_start": 6,
            "send_window_end": 22,
        }
    )


async def run_tick_with_user(utc_dt: datetime, user: User) -> MagicMock:
    """Run a tick and return the delivery_service mock."""
    mock_bot = MagicMock()
    mock_user_repo = MagicMock()
    mock_user_repo.list_all = AsyncMock(return_value=[user])

    mock_practice_repo = MagicMock()
    mock_send_repo = MagicMock()
    mock_send_repo.try_claim = AsyncMock(return_value=True)

    mock_practice_service = MagicMock()
    mock_practice_service.due_now = AsyncMock(return_value=[make_practice()])

    mock_delivery_service = MagicMock()
    mock_delivery_service.send = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    config = make_config()

    with (
        patch("bot.scheduler.datetime") as mock_datetime,
        patch("bot.scheduler.UserRepository", return_value=mock_user_repo),
        patch("bot.scheduler.PracticeRepository", return_value=mock_practice_repo),
        patch("bot.scheduler.PracticeSendRepository", return_value=mock_send_repo),
        patch("bot.scheduler.PracticeService", return_value=mock_practice_service),
        patch("bot.scheduler.DeliveryService", return_value=mock_delivery_service),
    ):
        mock_datetime.now.return_value = utc_dt
        mock_scheduler = MagicMock()
        await tick(mock_bot, mock_factory, config, mock_scheduler)

    return mock_delivery_service


@pytest.mark.asyncio
async def test_skip_day_silences_ticks_for_today() -> None:
    """After skip_until = today, ticks during the day send nothing."""
    today = date(2026, 6, 10)
    user = make_user(skip_until=today)
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    delivery_svc = await run_tick_with_user(utc_dt, user)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_day_also_silences_later_same_day() -> None:
    """skip_until == today silences all ticks until end of that local day."""
    today = date(2026, 6, 10)
    user = make_user(skip_until=today)
    utc_dt = datetime(2026, 6, 10, 21, 0, tzinfo=UTC)

    delivery_svc = await run_tick_with_user(utc_dt, user)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_next_day_resumes_after_skip() -> None:
    """The day after skip_until, practices resume."""
    yesterday = date(2026, 6, 9)
    user = make_user(skip_until=yesterday)
    # Now it's June 10 — skip_until < today
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    delivery_svc = await run_tick_with_user(utc_dt, user)
    delivery_svc.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_skip_sends_normally() -> None:
    """Without skip_until set, practices are sent normally."""
    user = make_user(skip_until=None)
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    delivery_svc = await run_tick_with_user(utc_dt, user)
    delivery_svc.send.assert_awaited_once()


# ---------------------------------------------------------------------------
# SkipDayService unit test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_day_service_sets_skip_until() -> None:
    """SkipDayService.skip_today sets skip_until to local today and commits."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    user = make_user()
    user_repo = MagicMock(spec=UserRepository)
    user_repo.get_by_telegram_id = AsyncMock(return_value=user)
    user_repo.save = AsyncMock(return_value=user)

    svc = SkipDayService(session, user_repo)

    with patch("bot.services.skip_day_service.datetime") as mock_dt:
        fixed_now = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
        mock_dt.now.return_value = fixed_now
        result = await svc.skip_today(123456789)

    assert result == date(2026, 6, 10)
    assert user.skip_until == date(2026, 6, 10)
    session.commit.assert_awaited_once()
