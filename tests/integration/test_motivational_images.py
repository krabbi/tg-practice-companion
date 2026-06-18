"""Integration tests for motivational image delivery (AC-17).

Tests:
- 2 image sends per day: morning at 06:00 via content_type=image (static file_id) and
  afternoon at 15:00 via content_type=motivational_image (random pool draw).
- Repeats allowed: the same pool image may be returned on consecutive days.
- Empty pool: the 15:00 tick claims the slot silently without calling send_photo.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.morning import MotivationalImage
from bot.models.practice import MediaAsset, Practice
from bot.models.user import User
from bot.scheduler import tick

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_USER_ID = 123456789
_MORNING_FILE_ID = "AgACmorning_image_file_id"
_POOL_FILE_ID = "AgACpool_image_file_id"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def img_config() -> Config:
    return Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": _TEST_DB_URL,
            "allowed_user_ids": str(_USER_ID),
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


def _make_user() -> User:
    u = User()
    u.telegram_id = _USER_ID
    u.timezone = "UTC"
    u.skip_until = None
    u.tz_changed_at = None
    u.language = "ru"
    return u


def _make_morning_image_practice(media_asset_id: uuid.UUID) -> Practice:
    """Morning image: static content_type=image practice at 06:00."""
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "Morning motivational image"
    p.content_type = "image"
    p.content = None
    p.media_asset_id = media_asset_id
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["06:00"]
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.active = True
    p.start_date = None
    p.end_date = None
    p.sort_order = 40
    p.user_id = _USER_ID
    return p


def _make_afternoon_practice() -> Practice:
    """Afternoon image: content_type=motivational_image draws from pool at 15:00."""
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "Afternoon motivational image"
    p.content_type = "motivational_image"
    p.content = None
    p.media_asset_id = None
    p.periodicity_type = "fixed_times"
    p.schedule_times = ["15:00"]
    p.anchor_hour = 0
    p.anchor_minute = 0
    p.active = True
    p.start_date = None
    p.end_date = None
    p.sort_order = 260
    p.user_id = _USER_ID
    return p


def _make_media_asset(telegram_file_id: str) -> MediaAsset:
    a = MediaAsset()
    a.id = uuid.uuid4()
    a.kind = "image"
    a.telegram_file_id = telegram_file_id
    a.storage_path = None
    a.mime = "image/jpeg"
    a.user_id = _USER_ID
    return a


def _make_pool_image(media_asset_id: uuid.UUID) -> MotivationalImage:
    img = MotivationalImage()
    img.id = uuid.uuid4()
    img.media_asset_id = media_asset_id
    img.active = True
    img.user_id = _USER_ID
    return img


@pytest.fixture
async def full_factory(session_factory) -> async_sessionmaker:
    """Seed user + morning image practice + afternoon practice + one pool image."""
    async with session_factory() as session:
        session.add(_make_user())

        morning_asset = _make_media_asset(_MORNING_FILE_ID)
        session.add(morning_asset)
        await session.flush()

        session.add(_make_morning_image_practice(morning_asset.id))
        session.add(_make_afternoon_practice())

        pool_asset = _make_media_asset(_POOL_FILE_ID)
        session.add(pool_asset)
        await session.flush()

        session.add(_make_pool_image(pool_asset.id))

        await session.commit()
    return session_factory


@pytest.fixture
async def afternoon_only_factory(session_factory) -> async_sessionmaker:
    """Seed user + afternoon practice only (no morning image, no pool — empty pool test)."""
    async with session_factory() as session:
        session.add(_make_user())
        session.add(_make_afternoon_practice())
        await session.commit()
    return session_factory


@pytest.fixture
async def afternoon_with_pool_factory(session_factory) -> async_sessionmaker:
    """Seed user + afternoon practice + one pool image (no morning image)."""
    async with session_factory() as session:
        session.add(_make_user())
        session.add(_make_afternoon_practice())

        pool_asset = _make_media_asset(_POOL_FILE_ID)
        session.add(pool_asset)
        await session.flush()

        session.add(_make_pool_image(pool_asset.id))
        await session.commit()
    return session_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_tick(
    factory: async_sessionmaker,
    config: Config,
    utc_dt: datetime,
    bot: MagicMock | None = None,
    scheduler: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock]:
    if bot is None:
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
    if scheduler is None:
        scheduler = MagicMock()
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_dt
        await tick(bot, factory, config, scheduler)
    return bot, scheduler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_image_sends_per_day(full_factory, img_config) -> None:
    """Morning (06:00) and afternoon (15:00) together produce exactly 2 send_photo calls (AC-17)."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    scheduler = MagicMock()

    # Morning tick — sends the static morning image
    await _run_tick(
        full_factory,
        img_config,
        datetime(2026, 6, 15, 6, 0, tzinfo=UTC),
        bot=bot,
        scheduler=scheduler,
    )
    assert bot.send_photo.await_count == 1, "Morning tick must send exactly one photo"
    morning_call = bot.send_photo.call_args_list[0]
    assert morning_call.kwargs.get("photo") == _MORNING_FILE_ID

    # Afternoon tick — draws from the pool and sends the pool image
    await _run_tick(
        full_factory,
        img_config,
        datetime(2026, 6, 15, 15, 0, tzinfo=UTC),
        bot=bot,
        scheduler=scheduler,
    )
    assert bot.send_photo.await_count == 2, "Afternoon tick must add a second photo send"
    afternoon_call = bot.send_photo.call_args_list[1]
    assert afternoon_call.kwargs.get("photo") == _POOL_FILE_ID


@pytest.mark.asyncio
async def test_afternoon_repeat_allowed(afternoon_with_pool_factory, img_config) -> None:
    """The same pool image may be sent on consecutive days (repeats allowed, AC-17)."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    scheduler = MagicMock()

    # Day 1 at 15:00
    await _run_tick(
        afternoon_with_pool_factory,
        img_config,
        datetime(2026, 6, 14, 15, 0, tzinfo=UTC),
        bot=bot,
        scheduler=scheduler,
    )
    assert bot.send_photo.await_count == 1

    # Day 2 at 15:00 — same pool image is the only option; must still be sent
    await _run_tick(
        afternoon_with_pool_factory,
        img_config,
        datetime(2026, 6, 15, 15, 0, tzinfo=UTC),
        bot=bot,
        scheduler=scheduler,
    )
    assert bot.send_photo.await_count == 2, "Pool image must be sent again on the next day"

    # Both sends used the pool image file_id
    for call in bot.send_photo.call_args_list:
        assert call.kwargs.get("photo") == _POOL_FILE_ID


@pytest.mark.asyncio
async def test_empty_pool_slot_claimed_silently(afternoon_only_factory, img_config) -> None:
    """When the pool is empty the slot is still claimed but send_photo is never called."""
    bot, _ = await _run_tick(
        afternoon_only_factory,
        img_config,
        datetime(2026, 6, 15, 15, 0, tzinfo=UTC),
    )
    bot.send_photo.assert_not_called()


@pytest.mark.asyncio
async def test_afternoon_dedup_no_double_send(afternoon_with_pool_factory, img_config) -> None:
    """A second tick at the same 15:00 slot does not re-send the pool image."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    scheduler = MagicMock()

    utc_dt = datetime(2026, 6, 15, 15, 0, tzinfo=UTC)

    await _run_tick(afternoon_with_pool_factory, img_config, utc_dt, bot=bot, scheduler=scheduler)
    count_after_first = bot.send_photo.await_count

    await _run_tick(afternoon_with_pool_factory, img_config, utc_dt, bot=bot, scheduler=scheduler)
    assert bot.send_photo.await_count == count_after_first, (
        "Second tick at the same 15:00 slot must not re-send"
    )
