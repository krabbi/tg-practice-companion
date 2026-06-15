"""Handler for good-deed evening reply capture (AC-10)."""

import logging
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot.i18n import DEFAULT_LANGUAGE, t
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.services.good_deed_service import GoodDeedService

logger = logging.getLogger(__name__)

_PROMPT_EXPIRY_HOURS = 24


async def _is_good_deeds_prompt(message: Message, prompt_repo: PendingPromptRepository) -> bool:
    """Return True when the newest unconsumed prompt is of kind 'good_deeds'.

    Used as a router-level filter so that messages without a pending good_deeds
    prompt fall through to the journal catch-all handler.
    """
    if message.from_user is None:
        return False
    not_before = datetime.now(UTC) - timedelta(hours=_PROMPT_EXPIRY_HOURS)
    prompt = await prompt_repo.newest_unconsumed(message.from_user.id, not_before=not_before)
    return prompt is not None and prompt.kind == "good_deeds"


def create_router() -> Router:
    """Create and return the good_deeds router."""
    router = Router(name="good_deeds")

    @router.message(StateFilter(None), F.text, _is_good_deeds_prompt)
    async def handle_good_deed_reply(
        message: Message,
        good_deed_service: GoodDeedService,
    ) -> None:
        """Capture the user's evening good-deed reply and store it."""
        if message.from_user is None or not message.text:
            return
        lang = DEFAULT_LANGUAGE
        try:
            await good_deed_service.store_today(message.from_user.id, message.text)
            await message.answer(t("good_deed_saved", lang))
        except Exception:
            logger.exception(
                "handle_good_deed_reply: failed to store deed for user %s",
                message.from_user.id,
            )
            await message.answer(t("good_deed_save_failed", lang))

    return router
