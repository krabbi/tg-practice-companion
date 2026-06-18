"""Unit tests for the good-deeds feature (AC-10).

Covers:
- GoodDeedService.store_today() — stores deed for local today, consumes pending prompt
- GoodDeedService.store_today() — invalid timezone falls back to UTC
- handle_good_deed_reply handler — happy path
- handle_good_deed_reply handler — service error path
- handle_good_deed_reply handler — no from_user
- _is_good_deeds_prompt filter — returns True when kind='good_deeds'
- _is_good_deeds_prompt filter — returns False when kind='thought'
- _is_good_deeds_prompt filter — returns False when no pending prompt
- _is_good_deeds_prompt filter — returns False when from_user is None
- tick sends good_deed question and writes pending_prompt when 'good_deeds' practice is due
- tick sends 15:00 text reminder (text practice)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.good_deeds import _is_good_deeds_prompt, create_router
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.models.journal import PendingPrompt
from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.user_repository import UserRepository
from bot.services.good_deed_service import GoodDeedService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_good_deed_service(
    session: AsyncSession | None = None,
    good_deed_repo: GoodDeedRepository | None = None,
    user_repo: UserRepository | None = None,
    prompt_repo: PendingPromptRepository | None = None,
) -> GoodDeedService:
    if session is None:
        session = MagicMock()
        session.commit = AsyncMock()
    if good_deed_repo is None:
        good_deed_repo = MagicMock(spec=GoodDeedRepository)
    if user_repo is None:
        user_repo = MagicMock(spec=UserRepository)
    if prompt_repo is None:
        prompt_repo = MagicMock(spec=PendingPromptRepository)
    return GoodDeedService(session, good_deed_repo, user_repo, prompt_repo)


def make_message(
    text: str = "Helped a neighbor",
    user_id: int | None = 123456789,
) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    if user_id is not None:
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
    else:
        msg.from_user = None
    return msg


def make_pending_prompt(kind: str = "good_deeds") -> MagicMock:
    prompt = MagicMock(spec=PendingPrompt)
    prompt.id = uuid.uuid4()
    prompt.kind = kind
    return prompt


def _get_handler(router_attr, name: str):
    for obs in router_attr.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    raise AssertionError(f"{name} handler not found in router")


# ---------------------------------------------------------------------------
# GoodDeedService.store_today() — with real SQLite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_today_creates_deed_for_local_date(db_session: AsyncSession) -> None:
    """store_today() inserts one GoodDeed with deed_date = local calendar date."""
    good_deed_repo = GoodDeedRepository(db_session)
    user_repo = UserRepository(db_session)
    prompt_repo = PendingPromptRepository(db_session)
    svc = GoodDeedService(db_session, good_deed_repo, user_repo, prompt_repo)

    from bot.models.user import User

    user = User()
    user.telegram_id = 1
    user.timezone = "UTC"
    user.skip_until = None
    user.tz_changed_at = None
    user.language = "ru"
    db_session.add(user)
    await db_session.commit()

    deed = await svc.store_today(user_id=1, text="Helped a neighbor")

    assert deed.id is not None
    assert deed.text == "Helped a neighbor"
    assert deed.user_id == 1
    assert deed.deed_date == datetime.now(UTC).date()


@pytest.mark.asyncio
async def test_store_today_consumes_pending_good_deeds_prompt(db_session: AsyncSession) -> None:
    """store_today() marks the newest good_deeds pending_prompt as consumed."""
    from bot.models.user import User

    good_deed_repo = GoodDeedRepository(db_session)
    user_repo = UserRepository(db_session)
    prompt_repo = PendingPromptRepository(db_session)
    svc = GoodDeedService(db_session, good_deed_repo, user_repo, prompt_repo)

    user = User()
    user.telegram_id = 2
    user.timezone = "UTC"
    user.skip_until = None
    user.tz_changed_at = None
    user.language = "ru"
    db_session.add(user)
    await db_session.commit()

    # Create a pending good_deeds prompt
    prompt = await prompt_repo.create(user_id=2, kind="good_deeds")
    await db_session.commit()
    assert not prompt.consumed

    await svc.store_today(user_id=2, text="Fed the cat")

    fetched = await db_session.get(PendingPrompt, prompt.id)
    assert fetched is not None
    assert fetched.consumed is True


@pytest.mark.asyncio
async def test_store_today_does_not_consume_thought_prompt(db_session: AsyncSession) -> None:
    """store_today() leaves thought-kind prompts unconsumed."""
    from bot.models.user import User

    good_deed_repo = GoodDeedRepository(db_session)
    user_repo = UserRepository(db_session)
    prompt_repo = PendingPromptRepository(db_session)
    svc = GoodDeedService(db_session, good_deed_repo, user_repo, prompt_repo)

    user = User()
    user.telegram_id = 3
    user.timezone = "UTC"
    user.skip_until = None
    user.tz_changed_at = None
    user.language = "ru"
    db_session.add(user)
    await db_session.commit()

    prompt = await prompt_repo.create(user_id=3, kind="thought")
    await db_session.commit()

    await svc.store_today(user_id=3, text="Volunteered")

    fetched = await db_session.get(PendingPrompt, prompt.id)
    assert fetched is not None
    assert fetched.consumed is False


@pytest.mark.asyncio
async def test_store_today_invalid_timezone_falls_back_to_utc(db_session: AsyncSession) -> None:
    """store_today() uses UTC when the user has an invalid timezone string."""
    from bot.models.user import User

    good_deed_repo = GoodDeedRepository(db_session)
    user_repo = UserRepository(db_session)
    prompt_repo = PendingPromptRepository(db_session)
    svc = GoodDeedService(db_session, good_deed_repo, user_repo, prompt_repo)

    user = User()
    user.telegram_id = 4
    user.timezone = "Not/ATimezone"
    user.skip_until = None
    user.tz_changed_at = None
    user.language = "ru"
    db_session.add(user)
    await db_session.commit()

    deed = await svc.store_today(user_id=4, text="Smiled at a stranger")

    assert deed.deed_date == datetime.now(UTC).date()


# ---------------------------------------------------------------------------
# _is_good_deeds_prompt filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_returns_true_when_good_deeds_prompt_exists() -> None:
    """_is_good_deeds_prompt returns True when the newest prompt has kind='good_deeds'."""
    msg = make_message()
    prompt = make_pending_prompt(kind="good_deeds")

    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=prompt)

    result = await _is_good_deeds_prompt(msg, prompt_repo)
    assert result is True


@pytest.mark.asyncio
async def test_filter_returns_false_when_prompt_is_thought() -> None:
    """_is_good_deeds_prompt returns False when the newest prompt has kind='thought'."""
    msg = make_message()
    prompt = make_pending_prompt(kind="thought")

    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=prompt)

    result = await _is_good_deeds_prompt(msg, prompt_repo)
    assert result is False


@pytest.mark.asyncio
async def test_filter_returns_false_when_no_prompt() -> None:
    """_is_good_deeds_prompt returns False when there is no unconsumed prompt."""
    msg = make_message()

    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=None)

    result = await _is_good_deeds_prompt(msg, prompt_repo)
    assert result is False


@pytest.mark.asyncio
async def test_filter_returns_false_when_no_from_user() -> None:
    """_is_good_deeds_prompt returns False when message.from_user is None."""
    msg = make_message(user_id=None)
    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.newest_unconsumed = AsyncMock()

    result = await _is_good_deeds_prompt(msg, prompt_repo)
    assert result is False
    prompt_repo.newest_unconsumed.assert_not_awaited()


# ---------------------------------------------------------------------------
# handle_good_deed_reply handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_happy_path() -> None:
    """handle_good_deed_reply stores the deed and replies with good_deed_saved."""
    router = create_router()
    handler = _get_handler(router.message, "handle_good_deed_reply")

    svc = MagicMock(spec=GoodDeedService)
    svc.store_today = AsyncMock()
    msg = make_message(text="Helped a neighbor")

    await handler(msg, good_deed_service=svc)

    svc.store_today.assert_awaited_once_with(123456789, "Helped a neighbor")
    msg.answer.assert_awaited_once_with(t("good_deed_saved", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_handler_service_error_replies_failed() -> None:
    """handle_good_deed_reply replies with good_deed_save_failed when service raises."""
    router = create_router()
    handler = _get_handler(router.message, "handle_good_deed_reply")

    svc = MagicMock(spec=GoodDeedService)
    svc.store_today = AsyncMock(side_effect=RuntimeError("DB error"))
    msg = make_message(text="Helped a neighbor")

    with patch("bot.handlers.good_deeds.logger"):
        await handler(msg, good_deed_service=svc)

    msg.answer.assert_awaited_once_with(t("good_deed_save_failed", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_handler_no_from_user_returns_early() -> None:
    """handle_good_deed_reply returns early when message.from_user is None."""
    router = create_router()
    handler = _get_handler(router.message, "handle_good_deed_reply")

    svc = MagicMock(spec=GoodDeedService)
    svc.store_today = AsyncMock()
    msg = make_message(user_id=None)

    await handler(msg, good_deed_service=svc)

    svc.store_today.assert_not_awaited()
    msg.answer.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tick integration: good_deeds practice writes pending_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_sends_good_deed_question_and_writes_prompt() -> None:
    """tick() sends the evening question and writes a good_deeds pending_prompt."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from bot.config import Config
    from bot.models.base import Base
    from bot.models.practice import Practice
    from bot.models.user import User
    from bot.scheduler import tick

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    config = Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "allowed_user_ids": "123456789",
            "send_window_start": 6,
            "send_window_end": 22,
        }
    )

    async with factory() as session:
        user = User()
        user.telegram_id = 123456789
        user.timezone = "UTC"
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        session.add(user)

        practice = Practice()
        practice.id = uuid.uuid4()
        practice.user_id = 123456789
        practice.name = "Good deed capture"
        practice.content_type = "good_deeds"
        practice.content = "Какое доброе дело ты сделала сегодня?"
        practice.periodicity_type = "fixed_times"
        practice.schedule_times = ["19:00"]
        practice.active = True
        practice.start_date = None
        practice.end_date = None
        practice.anchor_hour = 0
        practice.anchor_minute = 0
        practice.sort_order = 350
        practice.media_asset_id = None
        session.add(practice)

        await session.commit()

    sent_message = MagicMock()
    sent_message.message_id = 999

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=sent_message)
    scheduler = MagicMock()

    utc_7pm = datetime(2026, 6, 15, 19, 0, tzinfo=UTC)
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_7pm
        await tick(bot, factory, config, scheduler)

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs.get("chat_id") == 123456789
    assert "доброе дело" in (call_kwargs.get("text") or "")

    # Verify pending_prompt was created
    async with factory() as session:
        prompt_repo = PendingPromptRepository(session)
        prompt = await prompt_repo.newest_unconsumed(123456789)
        assert prompt is not None
        assert prompt.kind == "good_deeds"
        assert prompt.telegram_message_id == 999

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_tick_sends_15_reminder_as_text() -> None:
    """tick() sends the 15:00 good-deed reminder as a plain text message (no prompt written)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from bot.config import Config
    from bot.models.base import Base
    from bot.models.practice import Practice
    from bot.models.user import User
    from bot.scheduler import tick

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    config = Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeToken",
            "anthropic_api_key": "sk-ant-fake",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "allowed_user_ids": "123456789",
            "send_window_start": 6,
            "send_window_end": 22,
        }
    )

    async with factory() as session:
        user = User()
        user.telegram_id = 123456789
        user.timezone = "UTC"
        user.skip_until = None
        user.tz_changed_at = None
        user.language = "ru"
        session.add(user)

        practice = Practice()
        practice.id = uuid.uuid4()
        practice.user_id = 123456789
        practice.name = "Good deed reminder"
        practice.content_type = "text"
        practice.content = "Помни: сделай сегодня одно доброе дело!"
        practice.periodicity_type = "fixed_times"
        practice.schedule_times = ["15:00"]
        practice.active = True
        practice.start_date = None
        practice.end_date = None
        practice.anchor_hour = 0
        practice.anchor_minute = 0
        practice.sort_order = 250
        practice.media_asset_id = None
        session.add(practice)

        await session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()
    scheduler = MagicMock()

    utc_3pm = datetime(2026, 6, 15, 15, 0, tzinfo=UTC)
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_3pm
        await tick(bot, factory, config, scheduler)

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs.get("chat_id") == 123456789
    assert "доброе дело" in (call_kwargs.get("text") or "")

    # No pending prompt written for a text practice
    async with factory() as session:
        prompt_repo = PendingPromptRepository(session)
        prompt = await prompt_repo.newest_unconsumed(123456789)
        assert prompt is None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
