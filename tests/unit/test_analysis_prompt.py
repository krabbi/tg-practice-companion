"""Tests for the morning analysis LLM prompt content (AC-13).

Verifies that:
- The system prompt contains no-criticism / no-advice clause and supportive directive.
- The system prompt never contains practice-generation instructions.
- The user-turn prompt injects only the n-of-m numbers and target language.
- The LlmClient is called with the correct system string.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.journal_repository import DailyStats, JournalRepository
from bot.services.analysis_service import (
    _SYSTEM_PROMPT,
    AnalysisService,
)
from bot.services.llm_client import LlmClient
from bot.services.usage_service import UsageService

USER_ID = 111111
TARGET_DATE = date(2026, 6, 13)


# ---------------------------------------------------------------------------
# System-prompt content assertions (AC-13)
# ---------------------------------------------------------------------------


def test_system_prompt_forbids_criticism() -> None:
    """System prompt must explicitly forbid criticism (AC-13)."""
    assert "NEVER criticis" in _SYSTEM_PROMPT or "never criticis" in _SYSTEM_PROMPT.lower()


def test_system_prompt_forbids_unsolicited_advice() -> None:
    """System prompt must forbid unsolicited advice (AC-13)."""
    lower = _SYSTEM_PROMPT.lower()
    assert "unsolicited advice" in lower


def test_system_prompt_pins_supportive_tone() -> None:
    """System prompt must pin a supportive tone (AC-13)."""
    lower = _SYSTEM_PROMPT.lower()
    assert "supportive" in lower


def test_system_prompt_forbids_practice_generation() -> None:
    """System prompt must not instruct the LLM to generate practice content (AC-13)."""
    lower = _SYSTEM_PROMPT.lower()
    # The directive is a negation — we check that it contains 'not' alongside 'practice'
    assert "not" in lower and "practice" in lower


def test_system_prompt_has_no_practice_generation_affirmative() -> None:
    """System prompt must not contain affirmative practice-generation verbs (AC-13)."""
    forbidden_phrases = [
        "generate a practice",
        "create a practice",
        "write a practice",
        "suggest a practice",
        "design an exercise",
    ]
    lower = _SYSTEM_PROMPT.lower()
    for phrase in forbidden_phrases:
        assert phrase not in lower, f"System prompt must not contain: {phrase!r}"


# ---------------------------------------------------------------------------
# User-prompt content assertions
# ---------------------------------------------------------------------------


def test_user_prompt_contains_n_total_and_n_leads() -> None:
    """User prompt must include the exact n_total and n_leads numbers."""
    from bot.services.analysis_service import AnalysisService

    prompt = AnalysisService._build_user_prompt(n_total=5, n_leads=3, lang="ru")

    assert "5" in prompt
    assert "3" in prompt


def test_user_prompt_contains_language_name() -> None:
    """User prompt must specify the target language by name (not code)."""
    from bot.services.analysis_service import AnalysisService

    prompt_ru = AnalysisService._build_user_prompt(n_total=2, n_leads=1, lang="ru")
    prompt_en = AnalysisService._build_user_prompt(n_total=2, n_leads=1, lang="en")

    assert "Русский" in prompt_ru
    assert "English" in prompt_en


def test_user_prompt_does_not_contain_practice_generation_instruction() -> None:
    """User prompt must not ask the LLM to generate practices (AC-13)."""
    from bot.services.analysis_service import AnalysisService

    prompt = AnalysisService._build_user_prompt(n_total=4, n_leads=2, lang="ru")
    lower = prompt.lower()
    for phrase in ["generate a practice", "create an exercise", "suggest a technique"]:
        assert phrase not in lower, f"User prompt must not contain: {phrase!r}"


# ---------------------------------------------------------------------------
# LlmClient is called with the correct system string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_passes_system_prompt_to_llm(fake_config) -> None:
    """AnalysisService.build passes the exact _SYSTEM_PROMPT to the LLM (AC-13)."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.daily_stats = AsyncMock(return_value=DailyStats(n_total=3, n_leads=2))

    analysis_repo = MagicMock(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=None)
    analysis_repo.save = AsyncMock(side_effect=lambda a: a)

    usage_service = MagicMock(spec=UsageService)
    usage_service.month_to_date_cost = AsyncMock(return_value=Decimal("0"))
    usage_service.record = AsyncMock()

    mock_llm = MagicMock(spec=LlmClient)
    mock_llm.model = fake_config.llm_model
    fake_usage = anthropic.types.Usage(input_tokens=80, output_tokens=40)
    mock_llm.complete = AsyncMock(return_value=("You are doing great!", fake_usage))

    svc = AnalysisService(
        session=session,
        config=fake_config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )

    await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    mock_llm.complete.assert_awaited_once()
    call_kwargs = mock_llm.complete.call_args
    # The system argument must be the exact system prompt
    assert call_kwargs.kwargs.get("system") == _SYSTEM_PROMPT or (
        len(call_kwargs.args) >= 1 and call_kwargs.args[0] == _SYSTEM_PROMPT
    )


@pytest.mark.asyncio
async def test_build_records_usage_after_llm_call(fake_config) -> None:
    """AnalysisService.build records LLM usage via usage_service.record (AC-16)."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.daily_stats = AsyncMock(return_value=DailyStats(n_total=2, n_leads=1))

    analysis_repo = MagicMock(spec=AnalysisRepository)
    analysis_repo.get_by_user_and_date = AsyncMock(return_value=None)
    analysis_repo.save = AsyncMock(side_effect=lambda a: a)

    usage_service = MagicMock(spec=UsageService)
    usage_service.month_to_date_cost = AsyncMock(return_value=Decimal("0"))
    usage_service.record = AsyncMock()

    fake_usage = anthropic.types.Usage(input_tokens=120, output_tokens=60)
    mock_llm = MagicMock(spec=LlmClient)
    mock_llm.model = fake_config.llm_model
    mock_llm.complete = AsyncMock(return_value=("Keep going!", fake_usage))

    svc = AnalysisService(
        session=session,
        config=fake_config,
        journal_repo=journal_repo,
        analysis_repo=analysis_repo,
        llm_client=mock_llm,
        usage_service=usage_service,
    )

    await svc.build(user_id=USER_ID, analysis_date=TARGET_DATE, lang="ru")

    usage_service.record.assert_awaited_once()
    call_kwargs = usage_service.record.call_args
    assert call_kwargs.kwargs.get("usage") == fake_usage or (
        len(call_kwargs.args) >= 3 and call_kwargs.args[2] == fake_usage
    )
