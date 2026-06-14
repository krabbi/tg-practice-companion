"""Tests for the monthly cost guardrail in AnalysisService (AC-16).

Verifies that when month_to_date_cost + estimated_call_cost >= monthly_cost_limit_usd:
- LlmClient.complete is NOT called
- A deterministic localized fallback message is used
- A WARNING is logged
- The analysis row is still persisted (with the fallback message)
"""

import logging
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.journal_repository import DailyStats, JournalRepository
from bot.services.analysis_service import AnalysisService
from bot.services.llm_client import LlmClient
from bot.services.usage_service import UsageService

USER_ID = 222222
TARGET_DATE = date(2026, 6, 13)


def _make_service(
    *,
    fake_config,
    month_cost_usd: float,
    monthly_limit_usd: float | None = None,
) -> tuple[AnalysisService, MagicMock, MagicMock]:
    """Wire an AnalysisService with a fixed month-to-date cost."""
    from bot.config import Config

    if monthly_limit_usd is not None:
        config = Config.model_validate(
            {
                "telegram_bot_token": fake_config.telegram_bot_token,
                "anthropic_api_key": fake_config.anthropic_api_key,
                "database_url": fake_config.database_url,
                "allowed_user_ids": str(fake_config.allowed_user_ids[0]),
                "monthly_cost_limit_usd": monthly_limit_usd,
                "analysis_cost_cap_usd": fake_config.analysis_cost_cap_usd,
                "llm_model": fake_config.llm_model,
            }
        )
    else:
        config = fake_config

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.daily_stats = AsyncMock(return_value=DailyStats(n_total=3, n_leads=2))

    analysis_repo = MagicMock(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=None)
    analysis_repo.save = AsyncMock(side_effect=lambda a: a)

    usage_service = MagicMock(spec=UsageService)
    usage_service.month_to_date_cost = AsyncMock(return_value=Decimal(str(month_cost_usd)))
    usage_service.record = AsyncMock()

    mock_llm = MagicMock(spec=LlmClient)
    mock_llm.model = config.llm_model
    mock_llm.complete = AsyncMock(return_value=("LLM response", None))

    svc = AnalysisService(
        session=session,
        config=config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )
    return svc, mock_llm, session


# ---------------------------------------------------------------------------
# Guardrail fires: cost at/above limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardrail_fires_when_cost_equals_limit(fake_config) -> None:
    """When month_cost + estimate >= limit, LLM is NOT called (AC-16)."""
    # Set month_cost equal to the full limit so estimate pushes it over
    svc, mock_llm, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    mock_llm.complete.assert_not_awaited()
    assert result.used_fallback is True


@pytest.mark.asyncio
async def test_guardrail_fires_when_cost_exceeds_limit(fake_config) -> None:
    """When month_cost already exceeds the limit, LLM is NOT called (AC-16)."""
    svc, mock_llm, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd) + 1.0,
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    mock_llm.complete.assert_not_awaited()
    assert result.used_fallback is True


@pytest.mark.asyncio
async def test_guardrail_uses_deterministic_fallback_ru(fake_config) -> None:
    """Fallback message is the localized i18n string, not LLM output (AC-16)."""
    svc, _, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    assert result.message == t("analysis_fallback", "ru")


@pytest.mark.asyncio
async def test_guardrail_uses_deterministic_fallback_en(fake_config) -> None:
    """Fallback message is correctly localized for English as well."""
    svc, _, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="en")

    assert result.message == t("analysis_fallback", "en")


@pytest.mark.asyncio
async def test_guardrail_logs_warning(fake_config, caplog) -> None:
    """When the guardrail fires, a WARNING is logged (AC-16)."""
    svc, _, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    # Attach caplog's handler directly to the service logger instead of relying on
    # propagation to the root logger. Other tests in the full suite can leave global
    # logging state altered (root handlers / propagate flags); under pytest 9.1+'s
    # stricter capture isolation that made caplog.records come back empty here on CI
    # even though the WARNING was emitted (the bug that landed a red test on main).
    # Capturing at the source is immune to that cross-test pollution.
    svc_logger = logging.getLogger("bot.services.analysis_service")
    prev_level = svc_logger.level
    svc_logger.addHandler(caplog.handler)
    svc_logger.setLevel(logging.WARNING)
    try:
        await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")
    finally:
        svc_logger.removeHandler(caplog.handler)
        svc_logger.setLevel(prev_level)

    # Use record.getMessage() (computed on demand) rather than record.message: the
    # latter is only populated once a Formatter has formatted the record, which
    # pytest does not guarantee for captured records.
    assert any("guardrail" in record.getMessage().lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_guardrail_row_still_persisted(fake_config) -> None:
    """Even when the guardrail fires, a DailyAiAnalysis row is persisted."""
    svc, _, session = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    # analysis_repo.save was called once; session.commit was called once
    svc._analysis_repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert result.analysis_id is not None


# ---------------------------------------------------------------------------
# Guardrail does NOT fire: cost below limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardrail_does_not_fire_when_cost_is_zero(fake_config) -> None:
    """When month_cost is 0, the LLM IS called and no fallback is used."""
    import anthropic

    svc, mock_llm, _ = _make_service(fake_config=fake_config, month_cost_usd=0.0)
    fake_usage = anthropic.types.Usage(input_tokens=100, output_tokens=50)
    mock_llm.complete = AsyncMock(return_value=("You're amazing!", fake_usage))

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    mock_llm.complete.assert_awaited_once()
    assert result.used_fallback is False
    assert result.message == "You're amazing!"


@pytest.mark.asyncio
async def test_usage_record_called_when_guardrail_does_not_fire(fake_config) -> None:
    """When the LLM is called, usage_service.record is called once (AC-16)."""
    import anthropic

    svc, mock_llm, _ = _make_service(fake_config=fake_config, month_cost_usd=0.0)
    fake_usage = anthropic.types.Usage(input_tokens=100, output_tokens=50)
    mock_llm.complete = AsyncMock(return_value=("Keep it up!", fake_usage))

    await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    svc._usage_service.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_record_not_called_when_guardrail_fires(fake_config) -> None:
    """When the guardrail fires, usage_service.record is NOT called (AC-16)."""
    svc, _, _ = _make_service(
        fake_config=fake_config,
        month_cost_usd=float(fake_config.monthly_cost_limit_usd),
    )

    await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    svc._usage_service.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_exception_falls_back_to_deterministic_message(fake_config) -> None:
    """When the LLM call raises, the service falls back to the i18n message and persists."""
    from bot.i18n import t as _t

    svc, mock_llm, session = _make_service(fake_config=fake_config, month_cost_usd=0.0)
    # Make the LLM call raise
    mock_llm.complete = AsyncMock(side_effect=RuntimeError("Anthropic down"))

    result = await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    assert result.used_fallback is True
    assert result.message == _t("analysis_fallback", "ru")
    # Row is still persisted despite LLM failure
    svc._analysis_repo.save.assert_awaited_once()
    session.commit.assert_awaited_once()
