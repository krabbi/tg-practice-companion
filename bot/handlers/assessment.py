"""Handler for self-assessment inline button callbacks (AC-8)."""

import logging
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.exceptions import AssessmentError
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.assessment_service import AssessmentService

logger = logging.getLogger(__name__)


def create_router() -> Router:
    """Create and return the assessment router."""
    router = Router(name="assessment")

    @router.callback_query(F.data.startswith("assess:"))
    async def cb_assess(
        callback: CallbackQuery,
        assessment_service: AssessmentService,
    ) -> None:
        """Handle assess:{entry_id}:yes|no button presses."""
        await callback.answer()
        if callback.from_user is None or callback.message is None:
            return

        lang = DEFAULT_LANGUAGE

        # Parse callback data: "assess:<uuid>:yes" or "assess:<uuid>:no"
        parts = callback.data.split(":") if callback.data else []
        if len(parts) != 3 or parts[0] != "assess" or parts[2] not in ("yes", "no"):
            logger.warning("cb_assess: malformed callback data %r", callback.data)
            return

        try:
            entry_id = uuid.UUID(parts[1])
        except ValueError:
            logger.warning("cb_assess: invalid entry_id in callback data %r", callback.data)
            return

        leads_to_goals = parts[2] == "yes"

        try:
            await assessment_service.record(
                journal_entry_id=entry_id,
                leads_to_goals=leads_to_goals,
                set_via="button",
            )
        except AssessmentError as exc:
            logger.warning("cb_assess: assessment error for entry %s: %s", entry_id, exc)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(t("assessment_already_set", lang))
            return

        # Remove the inline keyboard after the user has responded
        await callback.message.edit_reply_markup(reply_markup=None)

    return router


def clarify_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    """Build the yes/no inline keyboard for a clarify follow-up question."""
    lang = DEFAULT_LANGUAGE
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("assess_yes", lang),
                    callback_data=f"assess:{entry_id}:yes",
                ),
                InlineKeyboardButton(
                    text=t("assess_no", lang),
                    callback_data=f"assess:{entry_id}:no",
                ),
            ]
        ]
    )
