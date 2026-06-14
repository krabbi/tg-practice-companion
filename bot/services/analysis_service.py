"""Daily AI morning analysis service (AC-11, AC-13, AC-16)."""

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.i18n import language_name, t
from bot.models.morning import DailyAiAnalysis
from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.journal_repository import JournalRepository
from bot.services.llm_client import LlmClient
from bot.services.usage_service import UsageKind, UsageService

logger = logging.getLogger(__name__)

# Maximum output tokens for the analysis LLM call (keeps costs predictable, AC-11).
_MAX_OUTPUT_TOKENS = 220

# Conservative token estimate for cost-guardrail pre-check: prompt size upper bound.
# A typical analysis prompt is well under 600 input tokens; we pad to 800 as a safe
# upper-bound so the guardrail fires before we actually hit the monthly cap.
_ESTIMATED_INPUT_TOKENS = 800

# System prompt text — pins supportive CBT tone, forbids criticism and unsolicited
# advice (AC-13).  The directive is intentional and must never be removed.
_SYSTEM_PROMPT = (
    "You are a warm, supportive CBT-informed companion. "
    "Your role is to encourage the user and celebrate their progress. "
    "You must NEVER criticise the user, point out flaws, or offer unsolicited advice. "
    "Write only kind, affirming, supportive sentences. "
    "Do not generate practice content or suggest specific exercises. "
    "Keep your response brief — two or three short sentences."
)


@dataclass(frozen=True)
class AnalysisResult:
    """Result returned by AnalysisService.build."""

    analysis_id: uuid.UUID
    message: str
    n_total: int
    n_leads: int
    used_fallback: bool


class AnalysisService:
    """Build and persist the once-daily morning AI analysis (AC-11).

    The service is idempotent per (user_id, analysis_date): if a row already
    exists it returns the existing message without calling the LLM again.
    """

    def __init__(
        self,
        session: AsyncSession,
        config: Config,
        journal_repo: JournalRepository,
        analysis_repo: AnalysisRepository,
        llm_client: LlmClient,
        usage_service: UsageService,
    ) -> None:
        self._session = session
        self._config = config
        self._journal_repo = journal_repo
        self._analysis_repo = analysis_repo
        self._llm_client = llm_client
        self._usage_service = usage_service

    async def build(
        self,
        user_id: int,
        analysis_date: date,
        lang: str,
        user_tz_name: str | None = None,
    ) -> AnalysisResult:
        """Build (or retrieve) the morning analysis for user_id on analysis_date.

        Steps:
        1. Idempotency check — return existing row if already built today.
        2. Query yesterday's stats (n_total, n_leads) from journal_entries.
        3. Cost-guardrail check (AC-16): if month_cost + estimate >= monthly cap,
           skip the LLM and send a deterministic localized fallback message.
        4. Call LlmClient with a supportive prompt (AC-13), record usage (AC-16).
        5. Persist a DailyAiAnalysis row; return AnalysisResult.
        """
        # --- Step 1: idempotency ---
        existing = await self._analysis_repo.get_by_user_and_date(user_id, analysis_date)
        if existing is not None:
            logger.info(
                "analysis_service: analysis for user=%s date=%s already exists, skipping",
                user_id,
                analysis_date,
            )
            return AnalysisResult(
                analysis_id=existing.id,
                message=existing.message,
                n_total=existing.n_total,
                n_leads=existing.n_leads,
                used_fallback=False,
            )

        # --- Step 2: stats ---
        stats = await self._journal_repo.daily_stats(user_id, analysis_date)
        n_total = stats.n_total
        n_leads = stats.n_leads

        # --- Step 3: cost guardrail ---
        used_fallback = False
        message: str

        month_cost = await self._usage_service.month_to_date_cost(user_tz_name)
        estimated_call_cost = self._estimate_call_cost()
        if month_cost + estimated_call_cost >= Decimal(str(self._config.monthly_cost_limit_usd)):
            logger.warning(
                "analysis_service: monthly cost guardrail triggered "
                "(month_cost=%.4f, estimate=%.6f, limit=%.2f) — using fallback",
                float(month_cost),
                float(estimated_call_cost),
                self._config.monthly_cost_limit_usd,
            )
            message = t("analysis_fallback", lang)
            used_fallback = True
        else:
            # --- Step 4: LLM call ---
            user_prompt = self._build_user_prompt(n_total, n_leads, lang)
            try:
                message, usage = await self._llm_client.complete(
                    system=_SYSTEM_PROMPT,
                    user=user_prompt,
                    max_tokens=_MAX_OUTPUT_TOKENS,
                )
                await self._usage_service.record(
                    kind=UsageKind.analysis,
                    model=self._llm_client.model,
                    usage=usage,
                )
            except Exception:
                logger.error(
                    "analysis_service: LLM call failed for user=%s date=%s — using fallback",
                    user_id,
                    analysis_date,
                    exc_info=True,
                )
                message = t("analysis_fallback", lang)
                used_fallback = True

        # --- Step 5: persist row ---
        analysis = DailyAiAnalysis()
        analysis.id = uuid.uuid4()
        analysis.user_id = user_id
        analysis.analysis_date = analysis_date
        analysis.n_total = n_total
        analysis.n_leads = n_leads
        analysis.message = message

        await self._analysis_repo.save(analysis)
        await self._session.commit()

        logger.info(
            "analysis_service: persisted analysis for user=%s date=%s "
            "(n_total=%d, n_leads=%d, fallback=%s)",
            user_id,
            analysis_date,
            n_total,
            n_leads,
            used_fallback,
        )

        return AnalysisResult(
            analysis_id=analysis.id,
            message=message,
            n_total=n_total,
            n_leads=n_leads,
            used_fallback=used_fallback,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _estimate_call_cost(self) -> Decimal:
        """Return a conservative cost estimate for one analysis call.

        Uses the upper-bound token estimate to pre-check the guardrail before
        the actual API call.  This avoids exceeding the cap by one call's worth.
        """
        from bot.services.usage_service import compute_llm_cost

        return compute_llm_cost(
            self._llm_client.model,
            input_tokens=_ESTIMATED_INPUT_TOKENS,
            output_tokens=_MAX_OUTPUT_TOKENS,
        )

    @staticmethod
    def _build_user_prompt(n_total: int, n_leads: int, lang: str) -> str:
        """Compose the user-turn prompt with yesterday's stats injected.

        Only the n-of-m numbers and the target language are injected; no user
        content or practice names ever enter the prompt (AC-13).
        """
        lang_name = language_name(lang)
        return (
            f"Yesterday the user wrote {n_total} journal entries. "
            f"Of those, {n_leads} were marked as leading towards their goals. "
            f"Write a brief, warm, supportive message for them in {lang_name}. "
            "Do not include criticism, unsolicited advice, or practice suggestions."
        )
