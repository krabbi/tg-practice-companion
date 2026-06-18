"""Integration test: timezone change reshapes schedule + backward-jump guard (AC-18).

Uses the same in-memory SQLite fixture as other integration tests.

Covers:
1. Timezone change mid-session: ticking at same UTC instant after tz change shifts which
   local-time slots are due (AC-18 recalc without restart).
2. Backward-jump (westward) guard: after a westward timezone change, slots whose local
   wall-time precede the tz_changed_at wall-time must not be claimed.
3. Forward jump (eastward): slots skipped, no catch-up.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.practice import Practice
from bot.models.user import User
from bot.repositories.user_repository import UserRepository
from bot.scheduler import tick

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
            "send_window_start": 0,  # wide-open window for test flexibility
            "send_window_end": 24,
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
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_user(factory: async_sessionmaker, timezone: str = "UTC") -> None:
    async with factory() as session:
        user = User()
        user.telegram_id = 123456789
        user.timezone = timezone
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        session.add(user)
        await session.commit()


async def _seed_practice(factory: async_sessionmaker, schedule_time: str = "10:00") -> Practice:
    async with factory() as session:
        p = Practice()
        p.id = uuid.uuid4()
        p.name = f"test-tz-practice-{schedule_time}"
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


async def _set_user_timezone(
    factory: async_sessionmaker, tz_string: str, tz_changed_at: datetime | None = None
) -> None:
    async with factory() as session:
        repo = UserRepository(session)
        user = await repo.get_first()
        assert user is not None
        user.timezone = tz_string
        user.tz_changed_at = tz_changed_at
        await repo.save(user)
        await session.commit()


def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


async def run_tick(
    factory: async_sessionmaker,
    config: Config,
    utc_dt: datetime,
    bot: MagicMock | None = None,
) -> MagicMock:
    if bot is None:
        bot = make_bot()
    scheduler = MagicMock()
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_dt
        await tick(bot, factory, config, scheduler)
    return bot


# ---------------------------------------------------------------------------
# Test 1: tz change mid-session reshapes due evaluation (AC-18 recalc)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timezone_change_reshapes_schedule_without_restart(session_factory, config) -> None:
    """After changing timezone, the next tick evaluates due practices in the new local time.

    Setup:
    - Practice fires at local 10:00.
    - UTC instant T1 = 2026-06-11 10:00 UTC; with tz=UTC → 10:00 local → FIRES.
    - Change tz to America/New_York (UTC-4).
    - UTC instant T2 = 2026-06-12 14:00 UTC; in New_York → 10:00 local → FIRES.
    - UTC instant T3 = 2026-06-12 10:00 UTC; in New_York → 06:00 local → NOT due.
    """
    await _seed_user(session_factory, timezone="UTC")
    await _seed_practice(session_factory, schedule_time="10:00")

    # T1: UTC 10:00 → UTC local 10:00 → practice due
    t1 = datetime(2026, 6, 11, 10, 0, tzinfo=UTC)
    bot1 = await run_tick(session_factory, config, t1)
    assert bot1.send_message.await_count == 1

    # Change timezone to America/New_York (UTC-4 in summer)
    # tz_changed_at in the past so it doesn't block future slots
    tz_changed = datetime(2026, 6, 11, 10, 0, tzinfo=UTC)
    await _set_user_timezone(session_factory, "America/New_York", tz_changed_at=tz_changed)

    # T2: UTC 14:00 on a NEW day → New_York 10:00 → practice due
    t2 = datetime(2026, 6, 12, 14, 0, tzinfo=UTC)
    bot2 = await run_tick(session_factory, config, t2)
    assert bot2.send_message.await_count == 1, "Practice should fire at UTC 14:00 (NY 10:00)"

    # T3: UTC 10:00 on same day → New_York 06:00 → NOT due for "10:00"
    t3 = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    bot3 = await run_tick(session_factory, config, t3)
    assert bot3.send_message.await_count == 0, "Practice must NOT fire at UTC 10:00 (NY 06:00)"


# ---------------------------------------------------------------------------
# Test 2: backward-jump guard prevents replay after westward tz change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backward_jump_guard_prevents_slot_replay(session_factory, config) -> None:
    """After a westward timezone change, slots whose local wall-time precedes
    tz_changed_at must not be claimed (no duplicate send).

    Scenario:
    - User is in Asia/Tokyo (UTC+9); practice fires at 10:00 local = UTC 01:00.
    - After tick at UTC 01:00 on day D, practice is claimed for slot "YYYY-MM-DDT10:00".
    - User changes tz to Europe/London (UTC+1 in summer, BST) at UTC 02:00 (= London 03:00).
      This is a westward (backward) jump: local wall-clock jumped back from UTC+9 to UTC+1.
      tz_changed_at = UTC 02:00; in London = 03:00 local.
    - Next tick at UTC 09:00 (same day): London local = 10:00 → slot "YYYY-MM-DDT10:00"
      local (London). slot_dt = 10:00; tz_change_local = 03:00 → 10:00 > 03:00 → guard passes.
    - Next tick at UTC 01:30 (same day, after tz change): London local = 02:30.
      slot "YYYY-MM-DDT02:30" local. tz_changed_at London = 03:00; 02:30 < 03:00 → BLOCKED.
    """
    # Use practice at 10:00 local
    await _seed_user(session_factory, timezone="Asia/Tokyo")
    await _seed_practice(session_factory, schedule_time="10:00")

    # Tick 1: UTC 01:00 = Tokyo 10:00 → practice fires
    t1 = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)
    bot1 = await run_tick(session_factory, config, t1)
    assert bot1.send_message.await_count == 1, "Practice should fire at Tokyo 10:00"

    # Simulate tz change to Europe/London (BST = UTC+1) at UTC 02:00 (London 03:00)
    tz_changed_at = datetime(2026, 6, 15, 2, 0, tzinfo=UTC)
    await _set_user_timezone(session_factory, "Europe/London", tz_changed_at=tz_changed_at)

    # Tick at UTC 01:30 (London BST = 02:30) — precedes tz_change_local (03:00) → BLOCKED
    # Practice at 10:00 is not due at 02:30, so no send expected anyway —
    # but the guard would fire if it were. Confirm by using a second practice at 02:30.
    await _seed_practice(session_factory, schedule_time="02:30")

    t2 = datetime(2026, 6, 15, 1, 30, tzinfo=UTC)  # London BST = 02:30
    bot2 = await run_tick(session_factory, config, t2)
    # slot_dt = 02:30 London; tz_change_local = 03:00 London → 02:30 < 03:00 → BLOCKED
    assert bot2.send_message.await_count == 0, (
        "Backward-jump guard must block slot at 02:30 London (precedes tz_changed_at 03:00)"
    )

    # Tick at UTC 09:00 (London BST = 10:00) — after tz_change_local (03:00) → NOT blocked
    t3 = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)  # London BST = 10:00
    bot3 = await run_tick(session_factory, config, t3)
    # slot_dt = 10:00 London; tz_change_local = 03:00 London → 10:00 > 03:00 → passes
    # But the slot "2026-06-15T10:00" was already claimed in Tokyo with the same slot_key!
    # The dedup guard (unique index) prevents re-sending. This is correct spec behaviour.
    assert bot3.send_message.await_count == 0, (
        "Slot 2026-06-15T10:00 was already claimed in Tokyo; dedup prevents re-send"
    )


# ---------------------------------------------------------------------------
# Test 3: forward jump — slots skipped, no catch-up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forward_jump_skips_slots_without_catch_up(session_factory, config) -> None:
    """A forward (eastward) timezone jump skips intermediate slots without sending them.

    Scenario:
    - Practice at 08:00 local.
    - User in UTC, last tick at UTC 07:00 (before 08:00).
    - Change tz to Asia/Tokyo (UTC+9). Now UTC 07:00 = Tokyo 16:00.
    - Tick at UTC 07:01 = Tokyo 16:01 → 08:00 slot is already 8 hours in the past in Tokyo.
    - The slot for "2026-06-15T08:00" local-Tokyo has not been sent — it's in the past,
      but no catch-up is expected. The slot is simply not due at 16:01.
    """
    await _seed_user(session_factory, timezone="UTC")
    await _seed_practice(session_factory, schedule_time="08:00")

    # Tick at UTC 07:00 (UTC local 07:00) → 08:00 not due
    t0 = datetime(2026, 6, 15, 7, 0, tzinfo=UTC)
    bot0 = await run_tick(session_factory, config, t0)
    assert bot0.send_message.await_count == 0

    # Change tz to Asia/Tokyo (UTC+9)
    tz_changed_at = datetime(2026, 6, 15, 7, 0, tzinfo=UTC)
    await _set_user_timezone(session_factory, "Asia/Tokyo", tz_changed_at=tz_changed_at)

    # Tick at UTC 07:01 = Tokyo 16:01; practice at 08:00 local is not due at 16:01
    t1 = datetime(2026, 6, 15, 7, 1, tzinfo=UTC)
    bot1 = await run_tick(session_factory, config, t1)
    assert bot1.send_message.await_count == 0, (
        "Forward jump must not send the skipped 08:00 slot at 16:01 (no catch-up)"
    )

    # Verify next day 08:00 Tokyo = UTC 23:00 does fire
    # UTC 23:00 on June 15 = Tokyo June 16 08:00
    t2 = datetime(2026, 6, 15, 23, 0, tzinfo=UTC)
    bot2 = await run_tick(session_factory, config, t2)
    assert bot2.send_message.await_count == 1, (
        "Practice must fire at the next legitimate 08:00 slot"
    )
