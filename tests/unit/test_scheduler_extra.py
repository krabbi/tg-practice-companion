"""Supplemental unit tests for bot/scheduler.py — branches not covered by test_scheduler_tick.py.

Covers:
- tick: invalid timezone → logs warning and returns early
- tick: backward-tz-jump guard blocks a slot that precedes tz_changed_at
- tick: delivery raises → logs error but does NOT re-raise (slot stays claimed)
- tick: outside send window → returns early
- housekeeping: calls prune_older_than and commits
- run_morning_analysis: dispatches analysis_service, sends message to user
"""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import Config
from bot.models.practice import Practice
from bot.models.user import User
from bot.scheduler import housekeeping, run_morning_analysis, tick

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


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


def make_user(
    timezone: str = "UTC",
    skip_until: date | None = None,
    tz_changed_at: datetime | None = None,
) -> User:
    u = User()
    u.telegram_id = 123456789
    u.timezone = timezone
    u.skip_until = skip_until
    u.tz_changed_at = tz_changed_at
    u.language = "ru"
    return u


def make_practice() -> Practice:
    p = Practice()
    p.id = uuid.uuid4()
    p.name = "extra test"
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


def make_session_factory(user: User | None = None, deliver_practices: bool = True) -> tuple:
    """Return (session_factory, mock repos) wired up for a single tick call."""
    mock_user_repo = MagicMock()
    mock_user_repo.list_all = AsyncMock(return_value=[user] if user is not None else [])

    mock_practice_repo = MagicMock()
    mock_send_repo = MagicMock()
    mock_send_repo.try_claim = AsyncMock(return_value=True)

    mock_practice_service = MagicMock()
    if deliver_practices:
        mock_practice_service.due_now = AsyncMock(return_value=[make_practice()])
    else:
        mock_practice_service.due_now = AsyncMock(return_value=[])

    mock_delivery_service = MagicMock()
    mock_delivery_service.send = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    return (
        mock_factory,
        mock_user_repo,
        mock_practice_repo,
        mock_send_repo,
        mock_practice_service,
        mock_delivery_service,
    )


async def run_tick_patched(
    utc_dt: datetime,
    user: User | None,
    deliver_practices: bool = True,
) -> tuple[MagicMock, MagicMock]:
    """Run tick with mocked internals; return (delivery_service, mock_scheduler)."""
    (
        mock_factory,
        mock_user_repo,
        mock_practice_repo,
        mock_send_repo,
        mock_practice_service,
        mock_delivery_service,
    ) = make_session_factory(user=user, deliver_practices=deliver_practices)

    config = make_config()
    mock_scheduler = MagicMock()
    mock_bot = MagicMock()

    with (
        patch("bot.scheduler.datetime") as mock_datetime,
        patch("bot.scheduler.UserRepository", return_value=mock_user_repo),
        patch("bot.scheduler.PracticeRepository", return_value=mock_practice_repo),
        patch("bot.scheduler.PracticeSendRepository", return_value=mock_send_repo),
        patch("bot.scheduler.PracticeService", return_value=mock_practice_service),
        patch("bot.scheduler.DeliveryService", return_value=mock_delivery_service),
    ):
        mock_datetime.now.return_value = utc_dt
        await tick(mock_bot, mock_factory, config, mock_scheduler)

    return mock_delivery_service, mock_scheduler


# ---------------------------------------------------------------------------
# Tests — tick edge branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_invalid_timezone_returns_early() -> None:
    """tick logs a warning and returns early when user.timezone is invalid."""
    user = make_user(timezone="Invalid/NotAZone")
    utc_dt = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)

    delivery_svc, _ = await run_tick_patched(utc_dt, user)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_outside_send_window_returns_early() -> None:
    """tick returns early (no sends) when local hour is outside the send window."""
    user = make_user(timezone="UTC")
    # 23:00 UTC — outside [6, 22)
    utc_dt = datetime(2026, 6, 12, 23, 0, tzinfo=UTC)

    delivery_svc, _ = await run_tick_patched(utc_dt, user)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_backward_tz_jump_guard_blocks_slot() -> None:
    """tick skips a slot whose local wall-time precedes the tz_changed_at wall-time."""
    # tz_changed_at at 11:00 UTC (= 11:00 local for UTC user)
    tz_changed_at = datetime(2026, 6, 12, 11, 0, tzinfo=UTC)
    user = make_user(timezone="UTC", tz_changed_at=tz_changed_at)

    # Tick is at 10:00 UTC — slot "10:00" precedes change wall-time "11:00"
    utc_dt = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)

    delivery_svc, _ = await run_tick_patched(utc_dt, user)
    delivery_svc.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_backward_tz_jump_guard_allows_slot_after_change() -> None:
    """tick allows a slot whose local wall-time is >= tz_changed_at wall-time."""
    # tz_changed_at at 09:00 UTC
    tz_changed_at = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)
    user = make_user(timezone="UTC", tz_changed_at=tz_changed_at)

    # Tick at 10:00 UTC — slot "10:00" is after change wall-time "09:00" → allowed
    utc_dt = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)

    delivery_svc, _ = await run_tick_patched(utc_dt, user)
    delivery_svc.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_delivery_failure_is_logged_not_raised() -> None:
    """tick logs delivery errors but does not re-raise them."""
    user = make_user(timezone="UTC")
    utc_dt = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)

    (
        mock_factory,
        mock_user_repo,
        mock_practice_repo,
        mock_send_repo,
        mock_practice_service,
        mock_delivery_service,
    ) = make_session_factory(user=user, deliver_practices=True)

    # Make delivery raise
    mock_delivery_service.send = AsyncMock(side_effect=Exception("Telegram error"))

    config = make_config()
    mock_bot = MagicMock()
    mock_scheduler = MagicMock()

    with (
        patch("bot.scheduler.datetime") as mock_datetime,
        patch("bot.scheduler.UserRepository", return_value=mock_user_repo),
        patch("bot.scheduler.PracticeRepository", return_value=mock_practice_repo),
        patch("bot.scheduler.PracticeSendRepository", return_value=mock_send_repo),
        patch("bot.scheduler.PracticeService", return_value=mock_practice_service),
        patch("bot.scheduler.DeliveryService", return_value=mock_delivery_service),
        patch("bot.scheduler.logger") as mock_logger,
    ):
        mock_datetime.now.return_value = utc_dt
        # Must not raise
        await tick(mock_bot, mock_factory, config, mock_scheduler)

    # The error must have been logged
    mock_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# housekeeping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_housekeeping_prunes_and_commits() -> None:
    """housekeeping calls prune_older_than and commits the session."""
    mock_send_repo = MagicMock()
    mock_send_repo.prune_older_than = AsyncMock(return_value=5)

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with (
        patch("bot.scheduler.datetime") as mock_datetime,
        patch("bot.scheduler.PracticeSendRepository", return_value=mock_send_repo),
    ):
        mock_datetime.now.return_value = datetime(2026, 6, 12, 3, 0, tzinfo=UTC)
        await housekeeping(mock_factory)

    mock_send_repo.prune_older_than.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# run_morning_analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_morning_analysis_skips_when_no_user() -> None:
    """run_morning_analysis returns early (no send) when user_id is not found in DB."""
    mock_user_repo = MagicMock()
    mock_user_repo.get_by_telegram_id = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    config = make_config()

    with patch("bot.scheduler.UserRepository", return_value=mock_user_repo):
        await run_morning_analysis(mock_bot, mock_factory, config, 123456789)

    mock_bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_morning_analysis_sends_message_to_user() -> None:
    """run_morning_analysis calls AnalysisService.build and sends the message."""
    from bot.services.analysis_service import AnalysisResult

    user = make_user(timezone="UTC")
    mock_user_repo = MagicMock()
    mock_user_repo.get_by_telegram_id = AsyncMock(return_value=user)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    import uuid

    fake_result = AnalysisResult(
        analysis_id=uuid.uuid4(),
        message="Great job yesterday!",
        n_total=3,
        n_leads=2,
        used_fallback=False,
    )
    mock_analysis_service = MagicMock()
    mock_analysis_service.build = AsyncMock(return_value=fake_result)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    config = make_config()

    with (
        patch("bot.scheduler.UserRepository", return_value=mock_user_repo),
        patch("bot.scheduler.AnalysisService", return_value=mock_analysis_service),
        patch("bot.scheduler.JournalRepository"),
        patch("bot.scheduler.AnalysisRepository"),
        patch("bot.scheduler.ApiUsageRepository"),
        patch("bot.scheduler.LlmClient"),
        patch("bot.scheduler.UsageService"),
    ):
        await run_morning_analysis(mock_bot, mock_factory, config, user.telegram_id)

    mock_analysis_service.build.assert_awaited_once()
    mock_bot.send_message.assert_awaited_once_with(user.telegram_id, "Great job yesterday!")


@pytest.mark.asyncio
async def test_run_morning_analysis_invalid_timezone_returns_early() -> None:
    """run_morning_analysis logs a warning and returns early for invalid timezone."""
    user = make_user(timezone="Invalid/Zone")
    mock_user_repo = MagicMock()
    mock_user_repo.get_by_telegram_id = AsyncMock(return_value=user)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    config = make_config()

    with patch("bot.scheduler.UserRepository", return_value=mock_user_repo):
        await run_morning_analysis(mock_bot, mock_factory, config, user.telegram_id)

    mock_bot.send_message.assert_not_awaited()
