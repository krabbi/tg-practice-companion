"""Usage logging and monthly cost guardrail (AC-16, AC-11)."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import anthropic

from bot.config import Config
from bot.models.morning import ApiUsageLog
from bot.repositories.api_usage_repository import ApiUsageRepository

logger = logging.getLogger(__name__)


class UsageKind:
    """String constants for ApiUsageLog.kind (mirrors the DB enum)."""

    analysis = "analysis"
    report = "report"
    transcription = "transcription"


# Per-model price table: model → (input_usd_per_token, output_usd_per_token).
# Prices sourced from https://www.anthropic.com/pricing (Haiku 4.5, 2025-10).
_LLM_PRICE_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5-20251001": (
        Decimal("0.0000008"),  # $0.80 per 1M input tokens
        Decimal("0.000004"),  # $4.00 per 1M output tokens
    ),
}

# Groq Whisper pricing: $0.111 per hour ≈ $3.083e-5 per second.
_GROQ_WHISPER_COST_PER_SECOND = Decimal("0.000030833")


def compute_llm_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Compute cost_usd for an LLM call using the price table.

    Raises ValueError for unknown models.
    """
    if model not in _LLM_PRICE_TABLE:
        raise ValueError(f"No price entry for model {model!r}")
    input_rate, output_rate = _LLM_PRICE_TABLE[model]
    return input_rate * input_tokens + output_rate * output_tokens


def compute_transcription_cost(audio_seconds: float) -> Decimal:
    """Compute cost_usd for a Groq Whisper transcription call."""
    return _GROQ_WHISPER_COST_PER_SECOND * Decimal(str(audio_seconds))


class UsageService:
    """Record API usage rows and expose the month-to-date cost sum (AC-16)."""

    def __init__(self, config: Config, api_usage_repo: ApiUsageRepository) -> None:
        self._config = config
        self._repo = api_usage_repo

    async def record(
        self,
        kind: str,
        model: str,
        usage: anthropic.types.Usage | None = None,
        audio_seconds: float | None = None,
        user_id: int | None = None,
    ) -> ApiUsageLog:
        """Compute cost_usd, insert an ApiUsageLog row, and return it.

        For LLM calls pass *usage* (the anthropic Usage object).
        For transcription calls pass *audio_seconds* instead.
        Pass *user_id* to associate the log row with a specific user.
        The caller is responsible for the surrounding transaction commit.
        """
        if usage is not None:
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cost_usd = compute_llm_cost(model, input_tokens, output_tokens)
        else:
            input_tokens = 0
            output_tokens = 0
            if audio_seconds is None:
                raise ValueError("Either usage or audio_seconds must be provided")
            cost_usd = compute_transcription_cost(audio_seconds)

        log = ApiUsageLog()
        log.id = uuid.uuid4()
        log.kind = kind
        log.model = model
        log.input_tokens = input_tokens
        log.output_tokens = output_tokens
        log.audio_seconds = audio_seconds
        log.cost_usd = cost_usd
        log.user_id = user_id

        logger.debug(
            "record: kind=%s model=%s cost_usd=%.6f",
            kind,
            model,
            float(cost_usd),
        )
        return await self._repo.save(log)

    async def month_to_date_cost(self, user_tz_name: str | None = None) -> Decimal:
        """Sum cost_usd for all rows in the current calendar month.

        Uses *user_tz_name* (IANA string) to determine month boundaries;
        falls back to UTC when None.
        """
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(user_tz_name) if user_tz_name else UTC
        now = datetime.now(tz)
        month_start = datetime(now.year, now.month, 1, tzinfo=tz).astimezone(UTC)
        return await self._repo.sum_cost_since(month_start)
