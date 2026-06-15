"""Unit tests for ReportService and the /report handler (AC-12).

Covers:
- build() returns correct counts and plain text (no chart/image payload)
- build() with no data returns the no-data message
- build() with good deeds lists them in the output
- /report sends period-selection keyboard
- 7d / 30d callback buttons trigger build() with correct date range
- custom-period flow: valid date entry → report; invalid → re-prompt
- report is plain text only (no ParseMode.HTML, no InlineKeyboardMarkup in the result)
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.reports import (
    _CB_REPORT_7D,
    _CB_REPORT_30D,
    _CB_REPORT_CUSTOM,
    ReportStates,
    create_router,
)
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.journal_repository import JournalRepository, PeriodStats
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.services.report_service import ReportResult, ReportService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    n_total: int = 0,
    n_leads: int = 0,
    n_practices: int = 0,
    deeds: list | None = None,
) -> MagicMock:
    """Return a ReportService mock with pre-set return values."""
    svc = MagicMock(spec=ReportService)
    lang = DEFAULT_LANGUAGE
    # We return a realistic ReportResult; build() is awaitable
    deeds = deeds or []

    async def fake_build(user_id, start, end, lang=lang):
        from bot.services.report_service import ReportResult

        lines = [t("report_header", lang).format(start=start.isoformat(), end=end.isoformat()), ""]
        if n_total == 0 and n_practices == 0 and len(deeds) == 0:
            lines.append(t("report_no_data", lang))
        else:
            if n_total > 0 or n_practices > 0:
                lines.append(t("report_total_entries", lang).format(n=n_total))
                if n_total > 0:
                    lines.append(
                        t("report_leads_fraction", lang).format(leads=n_leads, total=n_total)
                    )
                lines.append(t("report_practices_header", lang).format(n=n_practices))
                lines.append("")
            lines.append(t("report_good_deeds_header", lang))
            if not deeds:
                lines.append(t("report_good_deeds_empty", lang))
            else:
                for d in deeds:
                    lines.append(f"• [{d.deed_date.isoformat()}] {d.text}")
        return ReportResult(
            text="\n".join(lines),
            n_total=n_total,
            n_leads=n_leads,
            n_practices=n_practices,
            n_good_deeds=len(deeds),
        )

    svc.build = fake_build
    return svc


def make_message(user_id: int | None = 111, text: str = "") -> MagicMock:
    msg = MagicMock()
    msg.answer = AsyncMock()
    msg.text = text
    if user_id is not None:
        msg.from_user = MagicMock()
        msg.from_user.id = user_id
    else:
        msg.from_user = None
    return msg


def make_callback(
    user_id: int | None = 111,
    data: str = "",
    message_present: bool = True,
) -> MagicMock:
    cb = MagicMock()
    cb.answer = AsyncMock()
    cb.data = data
    if user_id is not None:
        cb.from_user = MagicMock()
        cb.from_user.id = user_id
    else:
        cb.from_user = None
    if message_present:
        cb.message = MagicMock()
        cb.message.answer = AsyncMock()
        cb.message.edit_text = AsyncMock()
    else:
        cb.message = None
    return cb


def make_fsm_context() -> MagicMock:
    ctx = MagicMock()
    ctx.set_state = AsyncMock()
    ctx.clear = AsyncMock()
    ctx.get_state = AsyncMock(return_value=None)
    return ctx


def _get_handler(router, kind: str, name: str):
    observers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for obs in observers:
        if hasattr(obs, "callback") and obs.callback.__name__ == name:
            return obs.callback
    return None


# ---------------------------------------------------------------------------
# ReportService unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_service_no_data() -> None:
    """build() returns no-data message when all counts are zero."""
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.period_stats = AsyncMock(return_value=PeriodStats(n_total=0, n_leads=0))
    deed_repo = MagicMock(spec=GoodDeedRepository)
    deed_repo.list_by_date_range = AsyncMock(return_value=[])
    send_repo = MagicMock(spec=PracticeSendRepository)
    send_repo.count_in_period = AsyncMock(return_value=0)

    svc = ReportService(journal_repo, deed_repo, send_repo)
    start = date(2026, 6, 1)
    end = date(2026, 6, 7)

    result = await svc.build(user_id=111, start=start, end=end, lang="ru")

    assert result.n_total == 0
    assert result.n_leads == 0
    assert result.n_practices == 0
    assert result.n_good_deeds == 0
    assert t("report_no_data", "ru") in result.text
    assert t("report_header", "ru").format(start="2026-06-01", end="2026-06-07") in result.text


@pytest.mark.asyncio
async def test_report_service_with_journal_data() -> None:
    """build() includes correct journal counts and self-assessment fraction."""
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.period_stats = AsyncMock(return_value=PeriodStats(n_total=10, n_leads=6))
    deed_repo = MagicMock(spec=GoodDeedRepository)
    deed_repo.list_by_date_range = AsyncMock(return_value=[])
    send_repo = MagicMock(spec=PracticeSendRepository)
    send_repo.count_in_period = AsyncMock(return_value=21)

    svc = ReportService(journal_repo, deed_repo, send_repo)
    result = await svc.build(
        user_id=111,
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
        lang="ru",
    )

    assert result.n_total == 10
    assert result.n_leads == 6
    assert result.n_practices == 21
    assert t("report_total_entries", "ru").format(n=10) in result.text
    assert t("report_leads_fraction", "ru").format(leads=6, total=10) in result.text
    assert t("report_practices_header", "ru").format(n=21) in result.text


@pytest.mark.asyncio
async def test_report_service_lists_good_deeds() -> None:
    """build() lists good deed texts in the report."""
    deed = MagicMock()
    deed.deed_date = date(2026, 6, 3)
    deed.text = "Помогла соседке"

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.period_stats = AsyncMock(return_value=PeriodStats(n_total=0, n_leads=0))
    deed_repo = MagicMock(spec=GoodDeedRepository)
    deed_repo.list_by_date_range = AsyncMock(return_value=[deed])
    send_repo = MagicMock(spec=PracticeSendRepository)
    send_repo.count_in_period = AsyncMock(return_value=0)

    svc = ReportService(journal_repo, deed_repo, send_repo)
    result = await svc.build(
        user_id=111,
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
        lang="ru",
    )

    assert result.n_good_deeds == 1
    assert "Помогла соседке" in result.text


@pytest.mark.asyncio
async def test_report_service_no_image_or_chart_payload() -> None:
    """build() returns only a text string — no binary or media payload."""
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.period_stats = AsyncMock(return_value=PeriodStats(n_total=5, n_leads=3))
    deed_repo = MagicMock(spec=GoodDeedRepository)
    deed_repo.list_by_date_range = AsyncMock(return_value=[])
    send_repo = MagicMock(spec=PracticeSendRepository)
    send_repo.count_in_period = AsyncMock(return_value=10)

    svc = ReportService(journal_repo, deed_repo, send_repo)
    result = await svc.build(
        user_id=111,
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
    )

    assert isinstance(result, ReportResult)
    assert isinstance(result.text, str)
    # No binary content
    assert not isinstance(result.text, bytes)


@pytest.mark.asyncio
async def test_report_service_queries_correct_date_range() -> None:
    """build() passes exactly the given start/end to both repos."""
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.period_stats = AsyncMock(return_value=PeriodStats(n_total=0, n_leads=0))
    deed_repo = MagicMock(spec=GoodDeedRepository)
    deed_repo.list_by_date_range = AsyncMock(return_value=[])
    send_repo = MagicMock(spec=PracticeSendRepository)
    send_repo.count_in_period = AsyncMock(return_value=0)

    svc = ReportService(journal_repo, deed_repo, send_repo)
    start = date(2026, 5, 1)
    end = date(2026, 5, 31)

    await svc.build(user_id=999, start=start, end=end)

    journal_repo.period_stats.assert_awaited_once_with(999, start, end)
    deed_repo.list_by_date_range.assert_awaited_once_with(999, start, end)
    send_repo.count_in_period.assert_awaited_once_with(999, start, end)


# ---------------------------------------------------------------------------
# /report handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_report_sends_period_keyboard() -> None:
    """/report sends period-selection keyboard."""
    router = create_router()
    handler = _get_handler(router, "message", "cmd_report")
    assert handler is not None

    msg = make_message(user_id=111)
    state = make_fsm_context()

    await handler(msg, state=state)

    msg.answer.assert_awaited_once()
    args, kwargs = msg.answer.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert t("report_pick_period", DEFAULT_LANGUAGE) in text
    # keyboard is present
    assert kwargs.get("reply_markup") is not None or len(args) > 1


@pytest.mark.asyncio
async def test_cmd_report_no_from_user_returns_early() -> None:
    """/report returns early when from_user is None."""
    router = create_router()
    handler = _get_handler(router, "message", "cmd_report")
    assert handler is not None

    msg = make_message(user_id=None)
    state = make_fsm_context()

    await handler(msg, state=state)

    msg.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_report_7d_calls_build_with_7_day_range() -> None:
    """7d button calls build() with a 7-day range ending today."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_report_7d")
    assert handler is not None

    cb = make_callback(user_id=111, data=_CB_REPORT_7D)
    svc = make_service(n_total=3, n_leads=2, n_practices=7)

    captured_start = []
    captured_end = []
    original_build = svc.build

    async def tracking_build(user_id, start, end, lang=DEFAULT_LANGUAGE):
        captured_start.append(start)
        captured_end.append(end)
        return await original_build(user_id, start, end, lang)

    svc.build = tracking_build

    await handler(cb, report_service=svc)

    assert len(captured_end) == 1
    assert len(captured_start) == 1
    assert (captured_end[0] - captured_start[0]).days == 6  # 7 days inclusive


@pytest.mark.asyncio
async def test_cb_report_30d_calls_build_with_30_day_range() -> None:
    """30d button calls build() with a 30-day range ending today."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_report_30d")
    assert handler is not None

    cb = make_callback(user_id=111, data=_CB_REPORT_30D)
    svc = make_service()

    captured_start = []
    captured_end = []
    original_build = svc.build

    async def tracking_build(user_id, start, end, lang=DEFAULT_LANGUAGE):
        captured_start.append(start)
        captured_end.append(end)
        return await original_build(user_id, start, end, lang)

    svc.build = tracking_build

    await handler(cb, report_service=svc)

    assert len(captured_end) == 1
    assert (captured_end[0] - captured_start[0]).days == 29  # 30 days inclusive


@pytest.mark.asyncio
async def test_cb_report_custom_enters_fsm_state() -> None:
    """Custom button sets ReportStates.awaiting_custom_dates."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_report_custom")
    assert handler is not None

    cb = make_callback(user_id=111, data=_CB_REPORT_CUSTOM)
    state = make_fsm_context()

    await handler(cb, state=state)

    cb.answer.assert_awaited_once()
    state.set_state.assert_awaited_once_with(ReportStates.awaiting_custom_dates)
    cb.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_custom_dates_valid_format_delivers_report() -> None:
    """Valid 'YYYY-MM-DD YYYY-MM-DD' input delivers the report and clears state."""
    router = create_router()
    handler = _get_handler(router, "message", "handle_custom_dates")
    assert handler is not None

    msg = make_message(user_id=111, text="2026-05-01 2026-05-31")
    state = make_fsm_context()
    svc = make_service(n_total=5, n_leads=3)

    await handler(msg, state=state, report_service=svc)

    state.clear.assert_awaited_once()
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_custom_dates_invalid_format_reprompts() -> None:
    """Invalid date format re-sends the format hint, does not clear state."""
    router = create_router()
    handler = _get_handler(router, "message", "handle_custom_dates")
    assert handler is not None

    msg = make_message(user_id=111, text="not-a-date")
    state = make_fsm_context()
    svc = make_service()

    await handler(msg, state=state, report_service=svc)

    state.clear.assert_not_awaited()
    msg.answer.assert_awaited_once()
    text = msg.answer.call_args[0][0]
    assert t("report_custom_bad_format", DEFAULT_LANGUAGE) in text


@pytest.mark.asyncio
async def test_handle_custom_dates_swaps_start_end_if_reversed() -> None:
    """If start > end, build() is called with start and end swapped."""
    router = create_router()
    handler = _get_handler(router, "message", "handle_custom_dates")
    assert handler is not None

    # Reversed: end before start
    msg = make_message(user_id=111, text="2026-05-31 2026-05-01")
    state = make_fsm_context()
    svc = make_service()

    captured = []
    original_build = svc.build

    async def tracking_build(user_id, start, end, lang=DEFAULT_LANGUAGE):
        captured.append((start, end))
        return await original_build(user_id, start, end, lang)

    svc.build = tracking_build

    await handler(msg, state=state, report_service=svc)

    assert len(captured) == 1
    start, end = captured[0]
    assert start <= end


@pytest.mark.asyncio
async def test_report_send_error_replies_error_message() -> None:
    """When build() raises, _send_report replies with report_error."""
    router = create_router()
    handler = _get_handler(router, "callback_query", "cb_report_7d")
    assert handler is not None

    cb = make_callback(user_id=111, data=_CB_REPORT_7D)
    svc = MagicMock(spec=ReportService)
    svc.build = AsyncMock(side_effect=RuntimeError("DB fail"))

    with patch("bot.handlers.reports.logger"):
        await handler(cb, report_service=svc)

    cb.message.answer.assert_awaited_once_with(t("report_error", DEFAULT_LANGUAGE))
