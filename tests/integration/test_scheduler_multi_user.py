"""Integration tests for per-user scheduler iteration (issue #110).

Covers:
- Tick with two users in different timezones → each receives only their own due practices.
- One user's skip_until does not affect the other.
- Morning analysis dispatches one job per user; per-user job ids do not collide.
- A user with an invalid timezone is skipped without breaking the loop for valid users.
"""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.practice import Practice
from bot.models.user import User
from bot.scheduler import tick

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_USER_A_ID = 111111111  # timezone UTC
_USER_B_ID = 222222222  # timezone Europe/Moscow (UTC+3)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> Config:
    return Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": _TEST_DB_URL,
            "allowed_user_ids": f"{_USER_A_ID},{_USER_B_ID}",
            "send_window_start": 6,
            "send_window_end": 22,
        }
    )


@pytest.fixture
async def engine():
    e = create_async_engine(_TEST_DB_URL, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await e.dispose()


@pytest.fixture
async def session_factory(engine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


def _make_user(telegram_id: int, timezone: str, skip_until: date | None = None) -> User:
    u = User()
    u.telegram_id = telegram_id
    u.timezone = timezone
    u.skip_until = skip_until
    u.tz_changed_at = None
    u.language = "ru"
    return u


def _make_practice(user_id: int, schedule_time: str, sort_order: int = 0) -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = f"practice {user_id} {schedule_time}"
    p.content_type = "text"
    p.content = f"hello from {user_id}"
    p.periodicity_type = "fixed_times"
    p.schedule_times = [schedule_time]
    p.active = True
    p.start_date = None
    p.end_date = None
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.sort_order = sort_order
    p.media_asset_id = None
    p.user_id = user_id
    return p


async def run_tick_at(
    session_factory: async_sessionmaker,
    config: Config,
    utc_dt: datetime,
) -> tuple[MagicMock, MagicMock]:
    """Run one tick at utc_dt; return (bot_mock, scheduler_mock)."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    scheduler = MagicMock()
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_dt
        await tick(bot, session_factory, config, scheduler)
    return bot, scheduler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_users_different_timezones_receive_only_own_practices(
    session_factory, config
) -> None:
    """Tick at 10:00 UTC: UTC user gets their 10:00 practice; Moscow user (UTC+3, 13:00
    local) does NOT get their 10:00 local practice (which is due at 07:00 UTC instead).
    """
    async with session_factory() as s:
        s.add(_make_user(_USER_A_ID, "UTC"))
        s.add(_make_user(_USER_B_ID, "Europe/Moscow"))
        s.add(_make_practice(_USER_A_ID, "10:00"))
        s.add(_make_practice(_USER_B_ID, "10:00"))
        await s.commit()

    # 10:00 UTC = 10:00 for User A (UTC) and 13:00 for User B (Moscow)
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    bot, _ = await run_tick_at(session_factory, config, utc_dt)

    # Only User A should have received a practice at this UTC time
    assert bot.send_message.await_count == 1
    call = bot.send_message.call_args
    sent_to = call.kwargs.get("chat_id") or (call.args[0] if call.args else None)
    assert sent_to == _USER_A_ID, f"Expected message to User A ({_USER_A_ID}), got {sent_to}"


@pytest.mark.asyncio
async def test_skip_until_for_one_user_does_not_affect_other(session_factory, config) -> None:
    """One user's skip_until blocks only that user; the other user still receives practices."""
    async with session_factory() as s:
        # User A has skip_until set to today — no practices
        s.add(_make_user(_USER_A_ID, "UTC", skip_until=date(2026, 6, 10)))
        # User B has no skip_until — should receive practices normally
        s.add(_make_user(_USER_B_ID, "UTC"))
        s.add(_make_practice(_USER_A_ID, "10:00"))
        s.add(_make_practice(_USER_B_ID, "10:00"))
        await s.commit()

    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    bot, _ = await run_tick_at(session_factory, config, utc_dt)

    # Only User B receives the practice; User A is skipped
    assert bot.send_message.await_count == 1
    call = bot.send_message.call_args
    sent_to = call.kwargs.get("chat_id") or (call.args[0] if call.args else None)
    assert sent_to == _USER_B_ID, f"Expected message to User B ({_USER_B_ID}), got {sent_to}"


@pytest.mark.asyncio
async def test_morning_analysis_per_user_job_ids_do_not_collide(session_factory, config) -> None:
    """At 06:00 UTC both users (both in UTC) get their own morning_analysis job with
    distinct ids so replace_existing=True cannot clobber each other's job.
    """
    async with session_factory() as s:
        s.add(_make_user(_USER_A_ID, "UTC"))
        s.add(_make_user(_USER_B_ID, "UTC"))
        await s.commit()

    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)
    _, scheduler = await run_tick_at(session_factory, config, utc_dt)

    # Two add_job calls (one per user)
    assert scheduler.add_job.call_count == 2

    job_ids = [call.kwargs.get("id", "") for call in scheduler.add_job.call_args_list]
    assert len(set(job_ids)) == 2, f"Expected two distinct job ids, got {job_ids}"
    for job_id in job_ids:
        assert job_id.startswith("morning_"), f"Job id {job_id!r} should start with 'morning_'"


@pytest.mark.asyncio
async def test_invalid_timezone_user_skipped_valid_user_still_receives(
    session_factory, config
) -> None:
    """A user with an invalid timezone is skipped; the next valid user still gets their
    practices. One user's bad timezone must not abort the loop.
    """
    async with session_factory() as s:
        # User A has an invalid timezone
        s.add(_make_user(_USER_A_ID, "Not/AReal/Zone"))
        # User B has a valid timezone
        s.add(_make_user(_USER_B_ID, "UTC"))
        s.add(_make_practice(_USER_A_ID, "10:00"))
        s.add(_make_practice(_USER_B_ID, "10:00"))
        await s.commit()

    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    bot, _ = await run_tick_at(session_factory, config, utc_dt)

    # User A is skipped (invalid TZ); User B receives their practice
    assert bot.send_message.await_count == 1
    call = bot.send_message.call_args
    sent_to = call.kwargs.get("chat_id") or (call.args[0] if call.args else None)
    assert sent_to == _USER_B_ID, (
        f"Expected only User B ({_USER_B_ID}) to receive a practice, got {sent_to}"
    )
