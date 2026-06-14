"""APScheduler setup: 60s tick job, housekeeping, and morning-analysis dispatch."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Config
from bot.models.practice import Practice
from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.api_usage_repository import ApiUsageRepository
from bot.repositories.blessing_repository import BlessingRepository
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.practice_repository import PracticeRepository
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.repositories.user_repository import UserRepository
from bot.services.analysis_service import AnalysisService
from bot.services.blessing_service import BlessingService
from bot.services.delivery_service import DeliveryService
from bot.services.llm_client import LlmClient
from bot.services.practice_service import PracticeService
from bot.services.usage_service import UsageService

logger = logging.getLogger(__name__)

# Housekeeping: prune practice_sends older than this many days
_PRUNE_DAYS = 14

# Local hour at which the morning block fires: blessing rotation + analysis dispatch (AC-3, AC-11)
_MORNING_BLOCK_HOUR = 6


def _slot_key(local_now: datetime) -> str:
    """Return the canonical slot key for the given local wall-clock minute.

    Format: "YYYY-MM-DDTHH:MM" — uniquely identifies a practice slot.
    """
    return local_now.strftime("%Y-%m-%dT%H:%M")


def compose(practices: list[Practice]) -> list[Practice]:
    """Sort due practices into the presentation order defined by sort_order ascending.

    The operator controls the morning-block sequence entirely through data:
    assign lower sort_order values to items that should be delivered first.
    Reference ordering (set in content/practices.yaml):
        blessing rotation (sent separately, before this loop)
        → morning practice   (sort_order ≤ 30)
        → motivational image (sort_order ≤ 40)
        → hourly question    (sort_order ≥ 100, after the morning block)
    """
    return sorted(practices, key=lambda p: p.sort_order)


async def run_morning_analysis(bot, session_factory: async_sessionmaker, config: Config) -> None:  # type: ignore[type-arg]
    """Run the morning AI analysis of yesterday's journal entries (AC-11).

    Dispatched as a separate one-shot APScheduler job (never awaited inline in
    tick) so that slow LLM calls cannot block the 60-second practice-delivery
    tick.  Idempotent per (user_id, analysis_date) — safe to re-dispatch.
    """
    logger.info("run_morning_analysis: starting")

    async with session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_first()
        if user is None:
            logger.info("run_morning_analysis: no user found, skipping")
            return

        tz_string = user.timezone or "UTC"
        try:
            user_tz = ZoneInfo(tz_string)
        except (ZoneInfoNotFoundError, KeyError):
            logger.warning(
                "run_morning_analysis: invalid timezone %r for user %s, skipping",
                tz_string,
                user.telegram_id,
            )
            return

        # analysis_date is *yesterday* in the user's local timezone
        now_local = datetime.now(UTC).astimezone(user_tz)
        analysis_date = (now_local - timedelta(days=1)).date()
        lang = user.language

        journal_repo = JournalRepository(session)
        analysis_repo = AnalysisRepository(session)
        api_usage_repo = ApiUsageRepository(session)
        llm_client = LlmClient(config)
        usage_service = UsageService(config, api_usage_repo)

        analysis_service = AnalysisService(
            session=session,
            config=config,
            journal_repo=journal_repo,
            analysis_repo=analysis_repo,
            llm_client=llm_client,
            usage_service=usage_service,
        )

        result = await analysis_service.build(
            user_id=user.telegram_id,
            analysis_date=analysis_date,
            lang=lang,
            user_tz_name=tz_string,
        )

        # Deliver the analysis message to the user via Telegram.
        try:
            await bot.send_message(user.telegram_id, result.message)
            logger.info(
                "run_morning_analysis: sent analysis to user %s "
                "(date=%s, n_total=%d, n_leads=%d, fallback=%s)",
                user.telegram_id,
                analysis_date,
                result.n_total,
                result.n_leads,
                result.used_fallback,
            )
        except Exception:
            logger.error(
                "run_morning_analysis: failed to send message to user %s",
                user.telegram_id,
                exc_info=True,
            )


async def tick(  # type: ignore[type-arg]
    bot,
    session_factory: async_sessionmaker,
    config: Config,
    scheduler: AsyncIOScheduler,
) -> None:
    """Evaluate due practices for the current UTC minute and send them.

    This job runs every 60 seconds with max_instances=1 and coalesce=True,
    so it can never overlap itself and a missed minute collapses into one run.

    At _MORNING_BLOCK_HOUR:00 local time the tick:
    1. Dispatches run_morning_analysis as a one-shot job (off-tick, never awaited).
    2. Sends the rotating morning blessing (inline, deduped by last_blessing_date).
    3. Delivers all other due practices in compose() order (sort_order ascending).
    """
    now_utc = datetime.now(UTC)

    async with session_factory() as session:
        user_repo = UserRepository(session)
        practice_repo = PracticeRepository(session)
        send_repo = PracticeSendRepository(session)
        prompt_repo = PendingPromptRepository(session)
        practice_service = PracticeService(practice_repo)
        delivery_service = DeliveryService(bot, prompt_repo=prompt_repo)

        user = await user_repo.get_first()
        if user is None:
            logger.debug("tick: no user found, skipping")
            return

        # Resolve local timezone — default to UTC if user hasn't set one yet
        tz_string = user.timezone or "UTC"
        try:
            user_tz = ZoneInfo(tz_string)
        except (ZoneInfoNotFoundError, KeyError):
            logger.warning(
                "tick: invalid timezone %r for user %s, skipping", tz_string, user.telegram_id
            )
            return

        local_now = now_utc.astimezone(user_tz)

        # Morning-block dispatch: fire once when the clock hits _MORNING_BLOCK_HOUR.
        # The analysis job is dispatched before the send-window check so it runs
        # regardless of any future send-window reconfiguration (AC-11).
        if local_now.hour == _MORNING_BLOCK_HOUR and local_now.minute == 0:
            scheduler.add_job(
                run_morning_analysis,
                "date",
                run_date=now_utc,
                args=[bot, session_factory, config],
                id="morning_analysis",
                replace_existing=True,
                max_instances=1,
            )
            logger.info("tick: dispatched morning_analysis one-shot job")

        # Send-window check: half-open [send_window_start, send_window_end)
        if not (config.send_window_start <= local_now.hour < config.send_window_end):
            logger.debug(
                "tick: outside send window (%02d:xx, window [%d, %d))",
                local_now.hour,
                config.send_window_start,
                config.send_window_end,
            )
            return

        # Skip-day check
        if user.skip_until is not None and user.skip_until >= local_now.date():
            logger.debug(
                "tick: skip_until=%s is active for user %s", user.skip_until, user.telegram_id
            )
            return

        # Morning blessing: sent once per calendar day at _MORNING_BLOCK_HOUR:00.
        # Deduped via user.last_blessing_date so a bot restart at :00 never double-sends.
        if (
            local_now.hour == _MORNING_BLOCK_HOUR
            and local_now.minute == 0
            and user.last_blessing_date != local_now.date()
        ):
            blessing_repo = BlessingRepository(session)
            blessing_svc = BlessingService(blessing_repo)
            blessing = await blessing_svc.for_date(local_now.date())
            if blessing is not None:
                # Claim before sending (same pattern as PracticeSend)
                user.last_blessing_date = local_now.date()
                await session.commit()
                try:
                    await bot.send_message(chat_id=user.telegram_id, text=blessing.text)
                    logger.info(
                        "tick: sent morning blessing (rotation_order=%d) to user %s",
                        blessing.rotation_order,
                        user.telegram_id,
                    )
                except Exception:
                    logger.error(
                        "tick: failed to send morning blessing to user %s",
                        user.telegram_id,
                        exc_info=True,
                    )

        due_practices = await practice_service.due_now(local_now)
        if not due_practices:
            logger.debug("tick: no practices due at %s", local_now.strftime("%H:%M"))
            return

        slot = _slot_key(local_now)

        for practice in compose(due_practices):
            # Capture scalar values up front — after session.commit() the ORM object
            # is expired; reading attributes after that would trigger a lazy-load.
            practice_id = practice.id
            practice_name = practice.name

            # Backward-tz-jump guard: refuse to claim a slot whose local wall-time
            # precedes the wall-time at the last timezone change.
            if user.tz_changed_at is not None:
                # Convert tz_changed_at (UTC) into the current zone
                tz_change_local = user.tz_changed_at.astimezone(user_tz)
                # Compare HH:MM strings: if the slot's wall-time precedes the change
                # wall-time, refuse to claim it (backward / westward jump guard)
                slot_dt = local_now.replace(second=0, microsecond=0)
                if slot_dt < tz_change_local.replace(second=0, microsecond=0):
                    logger.debug(
                        "tick: backward-tz-jump guard blocked slot %s for practice %s",
                        slot,
                        practice_id,
                    )
                    continue

            claimed = await send_repo.try_claim(
                practice_id=practice_id,
                user_id=user.telegram_id,
                slot_key=slot,
                sent_at=now_utc,
            )
            if not claimed:
                logger.debug(
                    "tick: slot %s for practice %s already claimed, skipping",
                    slot,
                    practice_id,
                )
                continue

            # Commit the claim before attempting delivery; if delivery fails we at
            # least avoid double-sending on the next tick (claimed row persists).
            await session.commit()

            try:
                await delivery_service.send(practice, user.telegram_id)
                # Commit to persist the pending_prompt written by DeliveryService
                # for question practices (flushed but not yet committed).
                await session.commit()
                logger.info(
                    "tick: delivered practice %s (%r) to user %s at slot %s",
                    practice_id,
                    practice_name,
                    user.telegram_id,
                    slot,
                )
            except Exception:
                logger.error(
                    "tick: delivery failed for practice %s at slot %s",
                    practice_id,
                    slot,
                    exc_info=True,
                )
                # Delivery failure is logged but does not un-claim the slot —
                # a failed send is still counted so we don't spam on the next tick.


async def housekeeping(session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
    """Prune practice_sends older than _PRUNE_DAYS days."""
    cutoff = datetime.now(UTC) - timedelta(days=_PRUNE_DAYS)
    async with session_factory() as session:
        send_repo = PracticeSendRepository(session)
        deleted = await send_repo.prune_older_than(cutoff)
        await session.commit()
        logger.info("housekeeping: pruned %d old practice_sends", deleted)


def start_scheduler(bot, session_factory: async_sessionmaker, config: Config) -> AsyncIOScheduler:  # type: ignore[type-arg]
    """Register the 60s tick and daily housekeeping jobs and start the scheduler.

    The tick job uses max_instances=1 and coalesce=True:
    - max_instances=1: a slow tick can never overlap itself
    - coalesce=True: missed minutes collapse into one re-evaluation (no catch-up)

    The scheduler reference is passed into tick so it can dispatch one-shot jobs
    (e.g. morning_analysis) without blocking the delivery loop.
    """
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        tick,
        "interval",
        seconds=60,
        args=[bot, session_factory, config, scheduler],
        id="practice_tick",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        housekeeping,
        "cron",
        hour=3,
        minute=0,
        args=[session_factory],
        id="housekeeping",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Scheduler started: tick every 60s, housekeeping daily at 03:00 UTC")
    return scheduler
