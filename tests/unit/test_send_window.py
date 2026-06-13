"""Unit tests for the send-window boundary convention.

AC-2 + boundary: half-open [send_window_start, send_window_end) in local time.
- 05:59 → outside window → nothing sent
- 22:00 → outside window (exclusive) → nothing sent
- 06:00 → inside window → practice sent
- 21:59 → inside window (last valid slot) → practice sent
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import Config
from bot.models.practice import Practice
from bot.models.user import User
from bot.scheduler import tick


def make_fixed_practice(time_str: str) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "window test practice"
    p.content_type = "text"
    p.content = "hello"
    p.periodicity_type = "fixed_times"
    p.schedule_times = [time_str]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = 0
    p.media_asset = None
    p.media_asset_id = None
    return p


def make_user(timezone: str = "UTC") -> User:
    u = User()
    u.telegram_id = 123456789
    u.timezone = timezone
    u.skip_until = None
    u.tz_changed_at = None
    u.language = "ru"
    return u


def make_config(start: int = 6, end: int = 22) -> Config:
    return Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "allowed_user_ids": "123456789",
            "send_window_start": start,
            "send_window_end": end,
        }
    )


async def run_tick_at(utc_dt: datetime, practice: Practice, config: Config) -> MagicMock:
    """Run a single tick at the given UTC datetime and return the mock bot."""
    user = make_user("UTC")  # UTC so local == utc_dt
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    mock_user_repo = MagicMock()
    mock_user_repo.get_first = AsyncMock(return_value=user)

    mock_practice_repo = MagicMock()
    mock_send_repo = MagicMock()
    mock_send_repo.try_claim = AsyncMock(return_value=True)
    mock_send_repo.prune_older_than = AsyncMock(return_value=0)

    mock_practice_service = MagicMock()
    mock_practice_service.due_now = AsyncMock(return_value=[practice])

    mock_delivery_service = MagicMock()
    mock_delivery_service.send = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    with (
        patch("bot.scheduler.datetime") as mock_datetime,
        patch("bot.scheduler.UserRepository", return_value=mock_user_repo),
        patch("bot.scheduler.PracticeRepository", return_value=mock_practice_repo),
        patch("bot.scheduler.PracticeSendRepository", return_value=mock_send_repo),
        patch("bot.scheduler.PracticeService", return_value=mock_practice_service),
        patch("bot.scheduler.DeliveryService", return_value=mock_delivery_service),
    ):
        mock_datetime.now.return_value = utc_dt
        await tick(mock_bot, mock_factory, config)

    return mock_delivery_service


@pytest.mark.asyncio
async def test_tick_at_0559_sends_nothing() -> None:
    """05:59 is outside [06:00, 22:00) — no send."""
    practice = make_fixed_practice("05:59")
    config = make_config()
    utc_dt = datetime(2026, 6, 10, 5, 59, tzinfo=UTC)
    delivery_svc = await run_tick_at(utc_dt, practice, config)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_at_2200_sends_nothing() -> None:
    """22:00 is the exclusive upper bound — no send."""
    practice = make_fixed_practice("22:00")
    config = make_config()
    utc_dt = datetime(2026, 6, 10, 22, 0, tzinfo=UTC)
    delivery_svc = await run_tick_at(utc_dt, practice, config)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_at_0600_sends() -> None:
    """06:00 is the inclusive lower bound — practice is sent."""
    practice = make_fixed_practice("06:00")
    config = make_config()
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)
    delivery_svc = await run_tick_at(utc_dt, practice, config)
    delivery_svc.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_at_2159_sends() -> None:
    """21:59 is the last valid slot — practice is sent."""
    practice = make_fixed_practice("21:59")
    config = make_config()
    utc_dt = datetime(2026, 6, 10, 21, 59, tzinfo=UTC)
    delivery_svc = await run_tick_at(utc_dt, practice, config)
    delivery_svc.send.assert_awaited_once()
