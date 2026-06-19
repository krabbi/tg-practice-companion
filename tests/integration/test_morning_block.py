"""Integration tests for the 06:00 morning block (AC-3, AC-11).

Tests:
- Blessing rotation: 06:00 tick sends a blessing from morning_blessings table.
- compose() ordering: morning practice (sort_order=30) delivered before hourly question
  (sort_order=100) — the 06:00 collision resolved by sort_order.
- Analysis dispatched as an off-tick APScheduler job, not awaited inline.
- Dedup: a second 06:00 tick on the same day does NOT resend blessing or practices.
- Consecutive mornings rotate through blessings in rotation_order sequence (AC-3).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.morning import MorningBlessing
from bot.models.practice import Practice
from bot.models.user import User
from bot.repositories.user_repository import UserRepository
from bot.scheduler import tick

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def morning_config() -> Config:
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
async def morning_factory(session_factory) -> async_sessionmaker:
    """Seed user + 3 blessings + morning practice (sort_order=30) + hourly question (sort_order=100)."""
    async with session_factory() as session:
        user = User()
        user.telegram_id = 123456789
        user.timezone = "UTC"
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        session.add(user)

        for i in range(1, 4):
            b = MorningBlessing()
            b.id = uuid.uuid4()
            b.text = f"Blessing {i}"
            b.rotation_order = i
            b.active = True
            b.user_id = 123456789
            session.add(b)

        # Morning practice at 06:00 — delivered first after blessing (sort_order=30)
        mp = Practice()
        mp.id = uuid.uuid4()
        mp.name = "Morning practice"
        mp.content_type = "text"
        mp.content = "Good morning practice!"
        mp.periodicity_type = "fixed_times"
        mp.schedule_times = ["06:00"]
        mp.active = True
        mp.start_date = None
        mp.end_date = None
        mp.anchor_hour = 0
        mp.anchor_minute = 0
        mp.sort_order = 30
        mp.media_asset_id = None
        mp.user_id = 123456789
        session.add(mp)

        # Hourly thought question — also fires at 06:00, delivered last (sort_order=100)
        # interval_hours=1, anchor_hour=0 → due every hour; 06:00 collision is intentional
        hq = Practice()
        hq.id = uuid.uuid4()
        hq.name = "Hourly thought question"
        hq.content_type = "text"
        hq.content = "What's on your mind?"
        hq.periodicity_type = "every_n_hours"
        hq.interval_hours = 1
        hq.anchor_hour = 0
        hq.anchor_minute = 0
        hq.schedule_times = None
        hq.active = True
        hq.start_date = None
        hq.end_date = None
        hq.sort_order = 100
        hq.media_asset_id = None
        hq.user_id = 123456789
        session.add(hq)

        await session.commit()

    return session_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def run_morning_tick(
    factory: async_sessionmaker,
    config: Config,
    utc_dt: datetime,
    bot: MagicMock | None = None,
    scheduler: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Run one tick at utc_dt; return (bot_mock, scheduler_mock)."""
    if bot is None:
        bot = MagicMock()
        bot.send_message = AsyncMock()
    if scheduler is None:
        scheduler = MagicMock()
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_dt
        await tick(bot, factory, config, scheduler)
    return bot, scheduler


def _extract_text(call) -> str:
    """Extract the text argument from a bot.send_message call (positional or keyword)."""
    if call.kwargs.get("text") is not None:
        return call.kwargs["text"]
    # positional: (chat_id, text) or (chat_id, text, ...)
    if len(call.args) > 1:
        return call.args[1]
    return ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_morning_block_blessing_sent_first(morning_factory, morning_config) -> None:
    """At 06:00 the blessing is sent as the very first message before any practice."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    bot, scheduler = await run_morning_tick(morning_factory, morning_config, utc_dt)

    # 3 sends: blessing + morning practice + hourly question
    assert bot.send_message.await_count == 3
    first_text = _extract_text(bot.send_message.call_args_list[0])
    assert first_text.startswith("Blessing"), f"Expected blessing first, got: {first_text!r}"


@pytest.mark.asyncio
async def test_morning_block_compose_order(morning_factory, morning_config) -> None:
    """06:00 block delivers practices in sort_order: morning practice (30) before hourly (100)."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    bot, _ = await run_morning_tick(morning_factory, morning_config, utc_dt)

    calls = bot.send_message.call_args_list
    assert len(calls) == 3

    texts = [_extract_text(c) for c in calls]
    assert texts[0].startswith("Blessing")  # blessing first
    assert texts[1] == "Good morning practice!"  # sort_order=30 before sort_order=100
    assert texts[2] == "What's on your mind?"  # hourly question last


@pytest.mark.asyncio
async def test_morning_analysis_dispatched_off_tick(morning_factory, morning_config) -> None:
    """Analysis is dispatched as a per-user APScheduler job, never awaited in tick."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    _, scheduler = await run_morning_tick(morning_factory, morning_config, utc_dt)

    scheduler.add_job.assert_called_once()
    job_id = scheduler.add_job.call_args.kwargs.get("id", "")
    assert job_id.startswith("morning_123456789_"), (
        f"Expected per-user job id starting with 'morning_123456789_', got {job_id!r}"
    )


@pytest.mark.asyncio
async def test_second_06_00_tick_deduped(morning_factory, morning_config) -> None:
    """A second 06:00 tick on the same day sends no duplicate messages (blessing + practices)."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    bot = MagicMock()
    bot.send_message = AsyncMock()
    scheduler = MagicMock()

    # First tick
    await run_morning_tick(morning_factory, morning_config, utc_dt, bot=bot, scheduler=scheduler)
    count_after_first = bot.send_message.await_count

    # Second tick at the same minute
    await run_morning_tick(morning_factory, morning_config, utc_dt, bot=bot, scheduler=scheduler)

    assert bot.send_message.await_count == count_after_first, (
        "Second tick at the same 06:00 slot should not send any messages"
    )


@pytest.mark.asyncio
async def test_consecutive_mornings_rotate_blessings(morning_factory, morning_config) -> None:
    """Consecutive mornings cycle through blessings in rotation_order sequence (AC-3)."""
    blessings_sent = []
    for day in range(1, 5):  # June 1–4 UTC
        utc_dt = datetime(2026, 6, day, 6, 0, tzinfo=UTC)
        bot, _ = await run_morning_tick(morning_factory, morning_config, utc_dt)
        first_text = _extract_text(bot.send_message.call_args_list[0])
        blessings_sent.append(first_text)

    # First 3 days: 3 distinct blessings (full rotation_order cycle)
    assert len(set(blessings_sent[:3])) == 3, (
        "Three consecutive mornings should yield three distinct blessings"
    )
    # 4th day wraps back to the same as day 1
    assert blessings_sent[3] == blessings_sent[0], (
        "Fourth morning should wrap back to the first blessing in the rotation"
    )


@pytest.mark.asyncio
async def test_hourly_question_after_morning_block(morning_factory, morning_config) -> None:
    """The 06:00 hourly-question collision is resolved: question is sent after the morning block."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    bot, _ = await run_morning_tick(morning_factory, morning_config, utc_dt)

    calls = bot.send_message.call_args_list
    assert len(calls) == 3

    # Hourly question must be last
    last_text = _extract_text(calls[-1])
    assert last_text == "What's on your mind?", (
        "Hourly question (sort_order=100) must be delivered after the morning block"
    )


@pytest.mark.asyncio
async def test_no_blessing_when_no_blessings_seeded(session_factory, morning_config) -> None:
    """If morning_blessings table is empty, no blessing is sent but practices still fire."""
    async with session_factory() as s:
        user = User()
        user.telegram_id = 123456789
        user.timezone = "UTC"
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        s.add(user)

        mp = Practice()
        mp.id = uuid.uuid4()
        mp.name = "Morning practice"
        mp.content_type = "text"
        mp.content = "Hello!"
        mp.periodicity_type = "fixed_times"
        mp.schedule_times = ["06:00"]
        mp.active = True
        mp.start_date = None
        mp.end_date = None
        mp.anchor_hour = 0
        mp.anchor_minute = 0
        mp.sort_order = 30
        mp.media_asset_id = None
        mp.user_id = 123456789
        s.add(mp)
        await s.commit()

    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)
    bot, _ = await run_morning_tick(session_factory, morning_config, utc_dt)

    # Practice delivered, no blessing (no blessings seeded)
    assert bot.send_message.await_count == 1
    text = _extract_text(bot.send_message.call_args_list[0])
    assert text == "Hello!"


@pytest.mark.asyncio
async def test_morning_block_uses_db_user_for_dedup(morning_factory, morning_config) -> None:
    """last_blessing_date is persisted in DB; a fresh session still deduplicates."""
    utc_dt = datetime(2026, 6, 10, 6, 0, tzinfo=UTC)

    # First tick — blessing sent and date persisted
    await run_morning_tick(morning_factory, morning_config, utc_dt)

    # Verify last_blessing_date was written
    async with morning_factory() as s:
        repo = UserRepository(s)
        user = await repo.get_first()
        assert user is not None
        from datetime import date

        assert user.last_blessing_date == date(2026, 6, 10)
