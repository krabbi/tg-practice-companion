"""Integration tests for the scheduler tick (AC-2 + AC-4 + dedup).

Uses an aiosqlite :memory: DB via the db_session fixture.

Covers:
- Due practice sends exactly once; second tick in the same slot does NOT resend (dedup).
- Adding a practice row between ticks → next tick sends it without restart (AC-4).
- Changing users.timezone between ticks → due evaluation shifts (AC-18 groundwork).
- Tick registered with max_instances=1 / coalesce=True.
- Morning analysis dispatched as a separate job (dispatch seam).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.practice import Practice
from bot.models.user import User
from bot.repositories.user_repository import UserRepository
from bot.scheduler import start_scheduler, tick

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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
            "allowed_user_ids": "123456789",
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


@pytest.fixture
async def seeded_session(session_factory) -> AsyncSession:
    """Yield a session with one user and one practice already inserted."""
    async with session_factory() as session:
        user = User()
        user.telegram_id = 123456789
        user.timezone = "UTC"
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        session.add(user)
        await session.commit()
    return session_factory


async def add_practice(session_factory, schedule_time: str = "10:00") -> Practice:
    """Insert a fixed-time practice into the DB and return it."""
    async with session_factory() as session:
        p = Practice()
        p.id = uuid.uuid4()
        p.name = f"test practice {schedule_time}"
        p.content_type = "text"
        p.content = "hello"
        p.periodicity_type = "fixed_times"
        p.schedule_times = [schedule_time]
        p.active = True
        p.start_date = None
        p.end_date = None
        p.anchor_hour = 0
        p.anchor_minute = 0
        p.sort_order = 0
        p.media_asset_id = None
        p.user_id = 123456789
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


async def run_tick(
    session_factory,
    config: Config,
    utc_dt: datetime,
    bot: MagicMock | None = None,
    scheduler: MagicMock | None = None,
) -> MagicMock:
    """Run one tick at utc_dt and return the bot mock."""
    if bot is None:
        bot = make_mock_bot()
    if scheduler is None:
        scheduler = MagicMock()
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_dt
        await tick(bot, session_factory, config, scheduler)
    return bot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_due_practice_sends_once(seeded_session, config) -> None:
    """A due practice is delivered exactly once per slot."""
    factory = seeded_session
    await add_practice(factory, "10:00")
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    bot = await run_tick(factory, config, utc_dt)
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_tick_same_slot_does_not_resend(seeded_session, config) -> None:
    """Second tick in the same slot must NOT resend (dedup via unique index)."""
    factory = seeded_session
    await add_practice(factory, "10:00")
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    bot = make_mock_bot()
    await run_tick(factory, config, utc_dt, bot=bot)
    await run_tick(factory, config, utc_dt, bot=bot)

    # Must have been called exactly once across both ticks
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_new_practice_added_between_ticks_hot_reloads(seeded_session, config) -> None:
    """Adding a practice between ticks takes effect on next tick without restart (AC-4)."""
    factory = seeded_session

    # First tick at 10:00 — no practices yet
    utc_first = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    bot = make_mock_bot()
    await run_tick(factory, config, utc_first, bot=bot)
    bot.send_message.assert_not_awaited()

    # Add a practice that fires at 11:00
    await add_practice(factory, "11:00")

    # Second tick at 11:00 — new practice should fire
    utc_second = datetime(2026, 6, 10, 11, 0, tzinfo=UTC)
    await run_tick(factory, config, utc_second, bot=bot)
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_timezone_change_shifts_due_evaluation(seeded_session, config) -> None:
    """Changing users.timezone between ticks shifts when practices are due (AC-18 groundwork).

    UTC user: practice at "10:00" is due at 10:00 UTC.
    After changing to Europe/Moscow (UTC+3), "10:00" local = 07:00 UTC.
    A tick at 10:00 UTC would be 13:00 Moscow time — not due for "10:00" local.
    """
    factory = seeded_session
    await add_practice(factory, "10:00")

    # Tick at 10:00 UTC while timezone is UTC → practice fires
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    bot = make_mock_bot()
    await run_tick(factory, config, utc_dt, bot=bot)
    assert bot.send_message.await_count == 1

    # Change timezone to Europe/Moscow (UTC+3)
    async with factory() as session:
        repo = UserRepository(session)
        user = await repo.get_first()
        assert user is not None
        user.timezone = "Europe/Moscow"
        await repo.save(user)
        await session.commit()

    # Tick at 07:00 UTC (= 10:00 Moscow) on a different date — practice fires again
    utc_moscow_10 = datetime(2026, 6, 11, 7, 0, tzinfo=UTC)
    bot2 = make_mock_bot()
    await run_tick(factory, config, utc_moscow_10, bot=bot2)
    bot2.send_message.assert_awaited_once()

    # Tick at 10:00 UTC (= 13:00 Moscow) on same date — practice is NOT due
    utc_moscow_13 = datetime(2026, 6, 11, 10, 0, tzinfo=UTC)
    bot3 = make_mock_bot()
    await run_tick(factory, config, utc_moscow_13, bot=bot3)
    bot3.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_scheduler_registers_tick_with_correct_options(config) -> None:
    """Tick job must be registered with max_instances=1 and coalesce=True."""
    mock_bot = make_mock_bot()
    mock_factory = MagicMock()

    scheduler = start_scheduler(mock_bot, mock_factory, config)
    try:
        tick_job = scheduler.get_job("practice_tick")
        assert tick_job is not None, "practice_tick job not found"
        assert tick_job.max_instances == 1
        assert tick_job.coalesce is True
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_morning_analysis_dispatched_as_separate_job(seeded_session, config) -> None:
    """At _MORNING_BLOCK_HOUR:00 local time, tick dispatches morning_analysis as a
    one-shot APScheduler job — never awaited inline.
    """
    factory = seeded_session
    # 06:00 UTC (user is in UTC, so local == UTC; morning block fires at hour 6)
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    mock_scheduler = MagicMock()
    await run_tick(factory, config, utc_dt, scheduler=mock_scheduler)

    # add_job must have been called with id="morning_analysis"
    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    # id is passed as a keyword argument
    assert call_kwargs.kwargs.get("id") == "morning_analysis" or (
        len(call_kwargs.args) > 3 and call_kwargs.args[3] == "morning_analysis"
    )


@pytest.mark.asyncio
async def test_morning_analysis_not_dispatched_outside_analysis_hour(
    seeded_session, config
) -> None:
    """At any hour other than _MORNING_ANALYSIS_HOUR, no morning_analysis job is dispatched."""
    factory = seeded_session
    # 10:00 UTC — inside send window but not the analysis hour
    utc_dt = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)

    mock_scheduler = MagicMock()
    await run_tick(factory, config, utc_dt, scheduler=mock_scheduler)

    mock_scheduler.add_job.assert_not_called()
