"""APScheduler setup: 60s tick job, housekeeping, and morning-analysis dispatch."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Config
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.practice_repository import PracticeRepository
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.repositories.user_repository import UserRepository
from bot.services.delivery_service import DeliveryService
from bot.services.practice_service import PracticeService

logger = logging.getLogger(__name__)

# Housekeeping: prune practice_sends older than this many days
_PRUNE_DAYS = 14

# Local hour at which the morning analysis is dispatched (once per day)
_MORNING_ANALYSIS_HOUR = 7


def _slot_key(local_now: datetime) -> str:
    """Return the canonical slot key for the given local wall-clock minute.

    Format: "YYYY-MM-DDTHH:MM" — uniquely identifies a practice slot.
    """
    return local_now.strftime("%Y-%m-%dT%H:%M")


async def run_morning_analysis(bot, session_factory: async_sessionmaker, config: Config) -> None:  # type: ignore[type-arg]
    """Run the morning AI analysis of yesterday's journal entries (AC-11).

    This is a no-op stub until the AI analysis service is implemented.
    It is intentionally dispatched as a separate one-shot APScheduler job
    (never awaited inline in tick) so that slow LLM calls cannot block the
    60-second practice-delivery tick.
    """
    logger.info("run_morning_analysis: stub — AI analysis service not yet implemented")


async def tick(  # type: ignore[type-arg]
    bot,
    session_factory: async_sessionmaker,
    config: Config,
    scheduler: AsyncIOScheduler,
) -> None:
    """Evaluate due practices for the current UTC minute and send them.

    This job runs every 60 seconds with max_instances=1 and coalesce=True,
    so it can never overlap itself and a missed minute collapses into one run.

    When the local clock first reaches _MORNING_ANALYSIS_HOUR, a one-shot
    run_morning_analysis job is dispatched to the scheduler (max_instances=1
    so concurrent dispatches are harmless).  Slow LLM work must never be
    awaited inline here.
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

        # Morning-analysis dispatch: fire once when the clock hits the analysis hour.
        # Dispatched as a separate one-shot job so the tick never blocks on LLM work.
        if local_now.hour == _MORNING_ANALYSIS_HOUR and local_now.minute == 0:
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

        due_practices = await practice_service.due_now(local_now)
        if not due_practices:
            logger.debug("tick: no practices due at %s", local_now.strftime("%H:%M"))
            return

        slot = _slot_key(local_now)

        for practice in due_practices:
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
