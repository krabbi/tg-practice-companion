"""Unit tests for the want-list feature (AC-9).

Covers:
- WantListService.add() — stores item and commits
- WantListService.list_active() — only undone items, oldest first
- WantListService.random_active() — None when empty, picks only undone items
- cmd_want handler — happy path, no text, error path, no from_user
- cmd_wants handler — happy path, empty list, error path, no from_user
- tick sends a random undone want item when a 'want' practice is due
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TCH002

from bot.handlers.want_list import create_router
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.repositories.want_list_repository import WantListRepository
from bot.services.want_list_service import WantListService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_want_service(
    session: AsyncSession | None = None,
    repo: WantListRepository | None = None,
) -> WantListService:
    """Build a WantListService backed by a mock session + real or mock repo."""
    if session is None:
        session = MagicMock()
        session.commit = AsyncMock()
    if repo is None:
        repo = MagicMock(spec=WantListRepository)
    return WantListService(session, repo)


def make_message(
    text: str = "/want hello",
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


# ---------------------------------------------------------------------------
# WantListService — unit (SQLite in-memory via db_session fixture)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_add_creates_item(db_session: AsyncSession) -> None:
    """add() inserts a new item and commits."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    item = await svc.add(user_id=1, text="Learn piano")

    assert item.id is not None
    assert item.text == "Learn piano"
    assert item.done is False

    fetched = await repo.get_by_id(item.id)
    assert fetched is not None
    assert fetched.text == "Learn piano"


@pytest.mark.asyncio
async def test_service_list_active_excludes_done(db_session: AsyncSession) -> None:
    """list_active() only returns items with done=False."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    item1 = await svc.add(user_id=2, text="Active item")
    done_item = await svc.add(user_id=2, text="Done item")
    await repo.mark_done(done_item.id)
    await db_session.commit()

    active = await svc.list_active(user_id=2)

    assert len(active) == 1
    assert active[0].id == item1.id


@pytest.mark.asyncio
async def test_service_list_active_empty(db_session: AsyncSession) -> None:
    """list_active() returns empty list when no undone items exist."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    result = await svc.list_active(user_id=999)
    assert result == []


@pytest.mark.asyncio
async def test_service_random_active_returns_none_when_empty(db_session: AsyncSession) -> None:
    """random_active() returns None when no undone items exist."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    result = await svc.random_active(user_id=3)
    assert result is None


@pytest.mark.asyncio
async def test_service_random_active_never_returns_done(db_session: AsyncSession) -> None:
    """random_active() never returns a done=True item."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    done = await svc.add(user_id=4, text="Done wish")
    await repo.mark_done(done.id)
    await db_session.commit()
    active = await svc.add(user_id=4, text="Active wish")

    for _ in range(20):
        picked = await svc.random_active(user_id=4)
        assert picked is not None
        assert picked.id == active.id
        assert picked.done is False


@pytest.mark.asyncio
async def test_service_random_active_returns_from_active_pool(db_session: AsyncSession) -> None:
    """random_active() picks uniformly from undone items (both items appear across runs)."""
    repo = WantListRepository(db_session)
    svc = WantListService(db_session, repo)

    item_a = await svc.add(user_id=5, text="Item A")
    item_b = await svc.add(user_id=5, text="Item B")

    seen_ids: set[uuid.UUID] = set()
    for _ in range(50):
        picked = await svc.random_active(user_id=5)
        assert picked is not None
        seen_ids.add(picked.id)

    assert item_a.id in seen_ids
    assert item_b.id in seen_ids


# ---------------------------------------------------------------------------
# cmd_want handler
# ---------------------------------------------------------------------------


def _get_handler(router_attr, name: str):
    """Extract a named handler function from a router's observers."""
    handler_func = None
    for obs in router_attr.handlers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            handler_func = obs.callback
            break
    assert handler_func is not None, f"{name} handler not found in router"
    return handler_func


@pytest.mark.asyncio
async def test_cmd_want_happy_path() -> None:
    """cmd_want adds item and replies with want_added."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_want")

    svc = MagicMock(spec=WantListService)
    svc.add = AsyncMock()
    msg = make_message(text="/want buy a guitar")

    await handler(msg, want_list_service=svc)

    svc.add.assert_awaited_once_with(123456789, "buy a guitar")
    msg.answer.assert_awaited_once_with(t("want_added", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_want_no_text_replies_hint() -> None:
    """cmd_want without text replies with want_no_text hint."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_want")

    svc = MagicMock(spec=WantListService)
    svc.add = AsyncMock()
    msg = make_message(text="/want")

    await handler(msg, want_list_service=svc)

    svc.add.assert_not_awaited()
    msg.answer.assert_awaited_once_with(t("want_no_text", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_want_service_error_replies_failed() -> None:
    """cmd_want replies with want_add_failed when service raises."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_want")

    svc = MagicMock(spec=WantListService)
    svc.add = AsyncMock(side_effect=RuntimeError("DB down"))
    msg = make_message(text="/want something")

    with patch("bot.handlers.want_list.logger"):
        await handler(msg, want_list_service=svc)

    msg.answer.assert_awaited_once_with(t("want_add_failed", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_want_no_from_user_returns_early() -> None:
    """cmd_want returns early when message.from_user is None."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_want")

    svc = MagicMock(spec=WantListService)
    svc.add = AsyncMock()
    msg = make_message(text="/want something", user_id=None)

    await handler(msg, want_list_service=svc)

    svc.add.assert_not_awaited()
    msg.answer.assert_not_awaited()


# ---------------------------------------------------------------------------
# cmd_wants handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_wants_lists_items() -> None:
    """cmd_wants replies with a numbered list when items exist."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_wants")

    item1 = MagicMock()
    item1.text = "Buy a guitar"
    item2 = MagicMock()
    item2.text = "Travel to Japan"
    svc = MagicMock(spec=WantListService)
    svc.list_active = AsyncMock(return_value=[item1, item2])
    msg = make_message(text="/wants")

    await handler(msg, want_list_service=svc)

    msg.answer.assert_awaited_once()
    sent = msg.answer.call_args[0][0]
    assert t("wants_list_header", DEFAULT_LANGUAGE) in sent
    assert "1. Buy a guitar" in sent
    assert "2. Travel to Japan" in sent


@pytest.mark.asyncio
async def test_cmd_wants_empty_list() -> None:
    """cmd_wants replies with wants_empty when no items exist."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_wants")

    svc = MagicMock(spec=WantListService)
    svc.list_active = AsyncMock(return_value=[])
    msg = make_message(text="/wants")

    await handler(msg, want_list_service=svc)

    msg.answer.assert_awaited_once_with(t("wants_empty", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_wants_service_error_replies_error() -> None:
    """cmd_wants replies with want_list_error when service raises."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_wants")

    svc = MagicMock(spec=WantListService)
    svc.list_active = AsyncMock(side_effect=RuntimeError("DB down"))
    msg = make_message(text="/wants")

    with patch("bot.handlers.want_list.logger"):
        await handler(msg, want_list_service=svc)

    msg.answer.assert_awaited_once_with(t("want_list_error", DEFAULT_LANGUAGE))


@pytest.mark.asyncio
async def test_cmd_wants_no_from_user_returns_early() -> None:
    """cmd_wants returns early when message.from_user is None."""
    router = create_router()
    handler = _get_handler(router.message, "cmd_wants")

    svc = MagicMock(spec=WantListService)
    svc.list_active = AsyncMock()
    msg = make_message(text="/wants", user_id=None)

    await handler(msg, want_list_service=svc)

    svc.list_active.assert_not_awaited()
    msg.answer.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tick integration: 12:00 want pick sends random undone item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_sends_want_pick_when_practice_due() -> None:
    """tick() sends a random undone want item when a 'want' practice is due.

    Asserts the core acceptance criterion: the scheduler dispatches the daily
    want pick to the user and never surfaces a done item.
    """
    from datetime import UTC, datetime

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from bot.config import Config
    from bot.models.base import Base
    from bot.models.lists import WantListItem
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

    # Seed: user + want practice + want-list items
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
        practice.name = "Daily want pick"
        practice.content_type = "want"
        practice.content = None
        practice.periodicity_type = "fixed_times"
        practice.schedule_times = ["12:00"]
        practice.active = True
        practice.start_date = None
        practice.end_date = None
        practice.anchor_hour = 0
        practice.anchor_minute = 0
        practice.sort_order = 150
        practice.media_asset_id = None
        session.add(practice)

        # Undone item — should be picked
        undone = WantListItem(user_id=123456789, text="Buy a guitar")
        session.add(undone)

        # Done item — must never be picked
        done = WantListItem(user_id=123456789, text="Already done", done=True)
        session.add(done)

        await session.commit()

    bot = MagicMock()
    bot.send_message = AsyncMock()
    scheduler = MagicMock()

    utc_noon = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    with patch("bot.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = utc_noon
        await tick(bot, factory, config, scheduler)

    bot.send_message.assert_awaited_once()
    call_text = bot.send_message.call_args.kwargs.get("text") or bot.send_message.call_args[1].get(
        "text"
    )
    assert "Buy a guitar" in call_text
    assert "Already done" not in call_text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
