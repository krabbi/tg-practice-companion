"""Handler for /skip_day command and 'Skip today' inline button (AC-5)."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.skip_day_service import SkipDayService

logger = logging.getLogger(__name__)

_CALLBACK_SKIP_TODAY = "skip_day:confirm"


def create_router() -> Router:
    """Create and return the skip_day router."""
    router = Router(name="skip_day")

    @router.message(Command("skip_day"))
    async def cmd_skip_day(
        message: Message,
        skip_day_service: SkipDayService,
    ) -> None:
        """Set skip_until = local today, silencing practices for the rest of the day."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        try:
            local_today = await skip_day_service.skip_today(message.from_user.id)
            await message.answer(t("skip_day_confirmed", lang).format(date=local_today.isoformat()))
        except Exception:
            logger.exception("cmd_skip_day: failed to skip day for user %s", message.from_user.id)
            await message.answer(t("skip_day_error", lang))

    @router.callback_query(F.data == _CALLBACK_SKIP_TODAY)
    async def cb_skip_today(
        callback: CallbackQuery,
        skip_day_service: SkipDayService,
    ) -> None:
        """Handle the 'Skip today' inline button press."""
        await callback.answer()
        if callback.from_user is None or callback.message is None:
            return
        lang = DEFAULT_LANGUAGE
        try:
            local_today = await skip_day_service.skip_today(callback.from_user.id)
            await callback.message.edit_text(
                t("skip_day_confirmed", lang).format(date=local_today.isoformat())
            )
        except Exception:
            logger.exception("cb_skip_today: failed to skip day for user %s", callback.from_user.id)
            await callback.message.edit_text(t("skip_day_error", lang))

    return router


def skip_today_keyboard() -> InlineKeyboardMarkup:
    """Return an inline keyboard with a single 'Skip today' button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("skip_day_button", DEFAULT_LANGUAGE), callback_data=_CALLBACK_SKIP_TODAY
                )
            ]
        ]
    )
