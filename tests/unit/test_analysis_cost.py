"""Tests for usage logging and cost computation (AC-16, AC-11).

Covers:
- compute_llm_cost: price table → cost ≤ analysis_cost_cap_usd for Haiku + ~220 output tokens
- UsageService.record: writes ApiUsageLog row with correct fields
- UsageService.month_to_date_cost: sums only the current month
"""

from decimal import Decimal

import anthropic
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.repositories.api_usage_repository import ApiUsageRepository
from bot.services.usage_service import (
    _LLM_PRICE_TABLE,
    UsageKind,
    UsageService,
    compute_llm_cost,
    compute_transcription_cost,
)

# ---------------------------------------------------------------------------
# Price table / cost computation
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5-20251001"


def test_haiku_in_price_table() -> None:
    """The pinned Haiku model must appear in the price table."""
    assert HAIKU_MODEL in _LLM_PRICE_TABLE


def test_analysis_shaped_call_within_cap() -> None:
    """A typical analysis call (≤1000 input + 220 output) stays under the $0.05 cap (AC-11)."""
    # Generous input budget: 1000 tokens covers a full morning journal summary prompt.
    cost = compute_llm_cost(HAIKU_MODEL, input_tokens=1000, output_tokens=220)
    assert cost <= Decimal("0.05"), f"Cost {cost} exceeds $0.05 cap"


def test_compute_llm_cost_zero_tokens() -> None:
    """Zero tokens produce zero cost."""
    cost = compute_llm_cost(HAIKU_MODEL, input_tokens=0, output_tokens=0)
    assert cost == Decimal("0")


def test_compute_llm_cost_unknown_model_raises() -> None:
    """Passing an unknown model raises ValueError."""
    with pytest.raises(ValueError, match="No price entry"):
        compute_llm_cost("gpt-99-turbo", input_tokens=100, output_tokens=50)


def test_compute_transcription_cost_positive() -> None:
    """Transcription cost is positive and proportional to audio_seconds."""
    cost_10s = compute_transcription_cost(10.0)
    cost_20s = compute_transcription_cost(20.0)
    assert cost_10s > Decimal("0")
    assert float(cost_20s) == pytest.approx(float(cost_10s) * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# UsageService.record — integration with in-memory DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_llm_call_writes_row(db_session: AsyncSession, fake_config: Config) -> None:
    """record() with an LLM usage object inserts a row with correct fields."""
    repo = ApiUsageRepository(db_session)
    service = UsageService(fake_config, repo)

    usage = anthropic.types.Usage(input_tokens=500, output_tokens=180)
    log = await service.record(kind=UsageKind.analysis, model=HAIKU_MODEL, usage=usage)

    assert log.id is not None
    assert log.kind == "analysis"
    assert log.model == HAIKU_MODEL
    assert log.input_tokens == 500
    assert log.output_tokens == 180
    assert log.audio_seconds is None
    expected_cost = compute_llm_cost(HAIKU_MODEL, 500, 180)
    assert float(log.cost_usd) == pytest.approx(float(expected_cost), rel=1e-6)


@pytest.mark.asyncio
async def test_record_transcription_call_writes_row(
    db_session: AsyncSession, fake_config: Config
) -> None:
    """record() with audio_seconds inserts a transcription row with correct fields."""
    repo = ApiUsageRepository(db_session)
    service = UsageService(fake_config, repo)

    log = await service.record(
        kind=UsageKind.transcription,
        model="whisper-large-v3-turbo",
        audio_seconds=30.0,
    )

    assert log.kind == "transcription"
    assert log.input_tokens == 0
    assert log.output_tokens == 0
    assert log.audio_seconds == pytest.approx(30.0)
    expected_cost = compute_transcription_cost(30.0)
    # Numeric(10,6) rounds to 6 decimal places; allow 1 ULP at that precision.
    assert float(log.cost_usd) == pytest.approx(float(expected_cost), abs=1e-6)


@pytest.mark.asyncio
async def test_record_raises_without_usage_or_audio(
    db_session: AsyncSession, fake_config: Config
) -> None:
    """record() with neither usage nor audio_seconds raises ValueError."""
    repo = ApiUsageRepository(db_session)
    service = UsageService(fake_config, repo)

    with pytest.raises(ValueError):
        await service.record(kind=UsageKind.analysis, model=HAIKU_MODEL)


# ---------------------------------------------------------------------------
# UsageService.month_to_date_cost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_month_to_date_cost_sums_current_month(
    db_session: AsyncSession, fake_config: Config
) -> None:
    """month_to_date_cost() sums rows in the current month and returns a Decimal."""
    repo = ApiUsageRepository(db_session)
    service = UsageService(fake_config, repo)

    # Write two rows (they'll have server-default now() timestamps → current month)
    usage = anthropic.types.Usage(input_tokens=100, output_tokens=50)
    await service.record(kind=UsageKind.analysis, model=HAIKU_MODEL, usage=usage)
    await service.record(kind=UsageKind.analysis, model=HAIKU_MODEL, usage=usage)

    total = await service.month_to_date_cost()
    assert isinstance(total, Decimal)
    expected = compute_llm_cost(HAIKU_MODEL, 100, 50) * 2
    assert float(total) == pytest.approx(float(expected), rel=1e-4)


@pytest.mark.asyncio
async def test_month_to_date_cost_returns_zero_when_empty(
    db_session: AsyncSession, fake_config: Config
) -> None:
    """month_to_date_cost() returns Decimal('0') when no rows exist."""
    repo = ApiUsageRepository(db_session)
    service = UsageService(fake_config, repo)

    total = await service.month_to_date_cost()
    assert total == Decimal("0")


# ---------------------------------------------------------------------------
# UsageKind constants
# ---------------------------------------------------------------------------


def test_usage_kind_values() -> None:
    """UsageKind constants match the DB enum values."""
    assert UsageKind.analysis == "analysis"
    assert UsageKind.report == "report"
    assert UsageKind.transcription == "transcription"
