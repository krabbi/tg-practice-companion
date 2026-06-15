"""Handler for /report command — on-demand period reports (AC-12, M5)."""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.report_service import ReportService

logger = logging.getLogger(__name__)

_CB_REPORT_7D = "report:7d"
_CB_REPORT_30D = "report:30d"
_CB_REPORT_CUSTOM = "report:custom"


def _period_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Return the period-selection inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("report_btn_7d", lang), callback_data=_CB_REPORT_7D),
                InlineKeyboardButton(text=t("report_btn_30d", lang), callback_data=_CB_REPORT_30D),
            ],
            [
                InlineKeyboardButton(
                    text=t("report_btn_custom", lang), callback_data=_CB_REPORT_CUSTOM
                ),
            ],
        ]
    )


class ReportStates(StatesGroup):
    """FSM states for the custom-period report flow."""

    awaiting_custom_dates = State()


def create_router() -> Router:
    """Create and return the reports router."""
    router = Router(name="reports")

    @router.message(Command("report"))
    async def cmd_report(message: Message, state: FSMContext) -> None:
        """Show the period-selection menu."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        # Clear any prior FSM state so a fresh /report always starts clean
        await state.clear()
        await message.answer(
            t("report_pick_period", lang),
            reply_markup=_period_keyboard(lang),
        )

    @router.callback_query(F.data == _CB_REPORT_7D)
    async def cb_report_7d(
        callback: CallbackQuery,
        report_service: ReportService,
    ) -> None:
        """Deliver the 7-day period report."""
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        end = date.today()
        start = end - timedelta(days=6)
        await _send_report(
            callback.message, callback.from_user.id, start, end, lang, report_service
        )

    @router.callback_query(F.data == _CB_REPORT_30D)
    async def cb_report_30d(
        callback: CallbackQuery,
        report_service: ReportService,
    ) -> None:
        """Deliver the 30-day period report."""
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        end = date.today()
        start = end - timedelta(days=29)
        await _send_report(
            callback.message, callback.from_user.id, start, end, lang, report_service
        )

    @router.callback_query(F.data == _CB_REPORT_CUSTOM)
    async def cb_report_custom(callback: CallbackQuery, state: FSMContext) -> None:
        """Ask the user to enter a custom date range."""
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        await state.set_state(ReportStates.awaiting_custom_dates)
        await callback.message.edit_text(t("report_custom_prompt", lang))

    @router.message(StateFilter(ReportStates.awaiting_custom_dates), F.text)
    async def handle_custom_dates(
        message: Message,
        state: FSMContext,
        report_service: ReportService,
    ) -> None:
        """Parse the user-entered date range and deliver the report."""
        if message.from_user is None or not message.text:
            return
        lang = DEFAULT_LANGUAGE
        parts = (message.text or "").strip().split()
        if len(parts) != 2:
            await message.answer(t("report_custom_bad_format", lang))
            return
        try:
            start = date.fromisoformat(parts[0])
            end = date.fromisoformat(parts[1])
        except ValueError:
            await message.answer(t("report_custom_bad_format", lang))
            return
        if start > end:
            start, end = end, start

        await state.clear()
        await _send_report(message, message.from_user.id, start, end, lang, report_service)

    return router


async def _send_report(
    message: Message,
    user_id: int,
    start: date,
    end: date,
    lang: str,
    report_service: ReportService,
) -> None:
    """Build and send the plain-text report; log and reply on error."""
    try:
        result = await report_service.build(user_id=user_id, start=start, end=end, lang=lang)
        await message.answer(result.text)
    except Exception:
        logger.exception("_send_report: failed for user %s, period %s – %s", user_id, start, end)
        await message.answer(t("report_error", lang))
