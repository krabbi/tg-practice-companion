"""Tests for AnalysisService stat computation (AC-11).

Verifies that daily_stats() counts n_total and n_leads correctly from seeded
JournalEntry + SelfAssessment rows, and that AnalysisService.build injects
those numbers into the persisted DailyAiAnalysis row.
"""

from datetime import UTC, date
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, SelfAssessment
from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.journal_repository import DailyStats, JournalRepository
from bot.services.analysis_service import AnalysisService
from bot.services.llm_client import LlmClient
from bot.services.usage_service import UsageService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = 123456
TARGET_DATE = date(2026, 6, 13)


async def _seed_entry(
    db_session: AsyncSession,
    user_id: int,
    entry_date: date,
    leads_to_goals: bool | None = None,
) -> JournalEntry:
    """Insert a JournalEntry (and optional SelfAssessment) into the test DB."""
    from datetime import datetime

    entry = JournalEntry()
    entry.user_id = user_id
    entry.text = "test entry"
    entry.source = "text"
    entry.practice_id = None
    entry.created_at = datetime(
        entry_date.year, entry_date.month, entry_date.day, 10, 0, 0, tzinfo=UTC
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)

    if leads_to_goals is not None:
        sa = SelfAssessment()
        sa.journal_entry_id = entry.id
        sa.leads_to_goals = leads_to_goals
        sa.set_via = "button"
        db_session.add(sa)
        await db_session.flush()

    return entry


# ---------------------------------------------------------------------------
# JournalRepository.daily_stats unit tests (integration with in-memory DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_stats_all_entries_lead(db_session: AsyncSession) -> None:
    """n_leads equals n_total when every entry is marked leads_to_goals=True."""
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=True)
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=True)

    repo = JournalRepository(db_session)
    stats = await repo.daily_stats(USER_ID, TARGET_DATE)

    assert stats.n_total == 2
    assert stats.n_leads == 2


@pytest.mark.asyncio
async def test_daily_stats_mixed(db_session: AsyncSession) -> None:
    """n_leads counts only True assessments; n_total counts all entries."""
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=True)
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=False)
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=None)  # no assessment

    repo = JournalRepository(db_session)
    stats = await repo.daily_stats(USER_ID, TARGET_DATE)

    assert stats.n_total == 3
    assert stats.n_leads == 1


@pytest.mark.asyncio
async def test_daily_stats_empty(db_session: AsyncSession) -> None:
    """Returns DailyStats(0, 0) when no entries exist for the date."""
    repo = JournalRepository(db_session)
    stats = await repo.daily_stats(USER_ID, TARGET_DATE)

    assert stats == DailyStats(n_total=0, n_leads=0)


@pytest.mark.asyncio
async def test_daily_stats_ignores_other_dates(db_session: AsyncSession) -> None:
    """Entries on a different date are not counted."""
    from datetime import date as _date

    other_date = _date(2026, 6, 12)
    await _seed_entry(db_session, USER_ID, other_date, leads_to_goals=True)
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=True)

    repo = JournalRepository(db_session)
    stats = await repo.daily_stats(USER_ID, TARGET_DATE)

    assert stats.n_total == 1
    assert stats.n_leads == 1


@pytest.mark.asyncio
async def test_daily_stats_ignores_other_users(db_session: AsyncSession) -> None:
    """Entries belonging to a different user are not counted."""
    other_user = 999999
    await _seed_entry(db_session, other_user, TARGET_DATE, leads_to_goals=True)
    await _seed_entry(db_session, USER_ID, TARGET_DATE, leads_to_goals=True)

    repo = JournalRepository(db_session)
    stats = await repo.daily_stats(USER_ID, TARGET_DATE)

    assert stats.n_total == 1
    assert stats.n_leads == 1


# ---------------------------------------------------------------------------
# AnalysisService.build — stats are propagated into the persisted row
# ---------------------------------------------------------------------------


def _make_analysis_service(
    *,
    n_total: int,
    n_leads: int,
    month_cost_usd: float = 0.0,
    fake_config,
) -> tuple[AnalysisService, MagicMock, MagicMock]:
    """Return (service, mock_llm, mock_session) wired with fixed stats."""
    from decimal import Decimal

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.daily_stats = AsyncMock(return_value=DailyStats(n_total=n_total, n_leads=n_leads))

    analysis_repo = MagicMock(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=None)
    # save returns the object passed in (simulate flush+refresh)
    analysis_repo.save = AsyncMock(side_effect=lambda a: a)

    usage_service = MagicMock(spec=UsageService)
    usage_service.month_to_date_cost = AsyncMock(return_value=Decimal(str(month_cost_usd)))
    usage_service.record = AsyncMock()

    mock_llm = MagicMock(spec=LlmClient)
    mock_llm.model = fake_config.llm_model
    fake_usage = anthropic.types.Usage(input_tokens=100, output_tokens=50)
    mock_llm.complete = AsyncMock(return_value=("Great job today!", fake_usage))

    svc = AnalysisService(
        session=session,
        config=fake_config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )
    return svc, mock_llm, session


@pytest.mark.asyncio
async def test_build_propagates_n_total_and_n_leads(fake_config) -> None:
    """AnalysisService.build returns the exact n_total/n_leads from the repo."""
    svc, _, _ = _make_analysis_service(n_total=7, n_leads=4, fake_config=fake_config)

    result = await svc.build(
        user_id=USER_ID,
        analysis_date=TARGET_DATE,
        lang="ru",
    )

    assert result.n_total == 7
    assert result.n_leads == 4


@pytest.mark.asyncio
async def test_build_persists_row(fake_config) -> None:
    """AnalysisService.build calls analysis_repo.save and session.commit."""
    from unittest.mock import MagicMock as _MM

    session = _MM(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = _MM(spec=JournalRepository)
    journal_repo.daily_stats = AsyncMock(return_value=DailyStats(n_total=3, n_leads=2))

    analysis_repo = _MM(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=None)
    analysis_repo.save = AsyncMock(side_effect=lambda a: a)

    from decimal import Decimal

    usage_service = _MM(spec=UsageService)
    usage_service.month_to_date_cost = AsyncMock(return_value=Decimal("0"))
    usage_service.record = AsyncMock()

    mock_llm = _MM(spec=LlmClient)
    mock_llm.model = fake_config.llm_model
    fake_usage = anthropic.types.Usage(input_tokens=80, output_tokens=40)
    mock_llm.complete = AsyncMock(return_value=("Wonderful!", fake_usage))

    svc = AnalysisService(
        session=session,
        config=fake_config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    analysis_repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert result.analysis_id is not None


@pytest.mark.asyncio
async def test_build_idempotent_returns_existing(fake_config) -> None:
    """build() returns existing row without calling LLM when already persisted."""
    import uuid as _uuid

    existing = MagicMock(spec=["id", "message", "n_total", "n_leads"])
    existing.id = _uuid.uuid4()
    existing.message = "Already done"
    existing.n_total = 5
    existing.n_leads = 3

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    analysis_repo = MagicMock(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=existing)

    usage_service = MagicMock(spec=UsageService)
    mock_llm = MagicMock(spec=LlmClient)
    mock_llm.complete = AsyncMock()

    svc = AnalysisService(
        session=session,
        config=fake_config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    mock_llm.complete.assert_not_awaited()
    assert result.message == "Already done"
    assert result.n_total == 5
    assert result.n_leads == 3
