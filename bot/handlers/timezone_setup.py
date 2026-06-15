"""Timezone picker FSM — continent → city selection (AC-18, M5).

The handler is registered *before* the journal F.text/F.voice catch-all so that
FSM input is never swallowed by the journal capture handler.  The journal handler
carries StateFilter(None) which yields to any active FSM state.

Callback prefixes:
  tzc:<continent>   — continent selected
  tzz:<iana_tz>     — final IANA timezone selected (URL-safe encoding)
"""

import logging
from zoneinfo import available_timezones

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.exceptions import TimezoneError
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.timezone_service import TimezoneService

logger = logging.getLogger(__name__)

# Callback data prefixes
_CB_CONTINENT = "tzc:"
_CB_CITY = "tzz:"

# Maximum inline keyboard buttons per row
_BUTTONS_PER_ROW = 2

# Continents we surface in the picker — derived from IANA names but ordered by relevance.
_CONTINENT_LABELS: dict[str, str] = {
    "Africa": "Africa",
    "America": "Americas",
    "Antarctica": "Antarctica",
    "Arctic": "Arctic",
    "Asia": "Asia",
    "Atlantic": "Atlantic",
    "Australia": "Australia / Pacific",
    "Europe": "Europe",
    "Indian": "Indian Ocean",
    "Pacific": "Pacific",
    "Etc": "Etc / Offsets",
}


def _build_tz_map() -> dict[str, list[str]]:
    """Build a mapping from continent prefix → sorted list of full IANA zone strings.

    Only zones that start with a known continent prefix are included.
    """
    mapping: dict[str, list[str]] = {c: [] for c in _CONTINENT_LABELS}
    for tz in sorted(available_timezones()):
        prefix = tz.split("/")[0]
        if prefix in mapping:
            mapping[prefix].append(tz)
    for zones in mapping.values():
        zones.sort()
    return mapping


# Eagerly build the map once at import time — this is cheap (in-process string ops).
_TZ_MAP: dict[str, list[str]] = _build_tz_map()


def _continent_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Return an inline keyboard with one button per continent."""
    buttons: list[InlineKeyboardButton] = []
    for key, label in _CONTINENT_LABELS.items():
        if _TZ_MAP.get(key):  # only show continents that have zones
            buttons.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{_CB_CONTINENT}{key}",
                )
            )
    rows = [buttons[i : i + _BUTTONS_PER_ROW] for i in range(0, len(buttons), _BUTTONS_PER_ROW)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _city_keyboard(continent: str) -> InlineKeyboardMarkup:
    """Return an inline keyboard listing all cities in the given continent."""
    zones = _TZ_MAP.get(continent, [])
    buttons: list[InlineKeyboardButton] = []
    for tz in zones:
        # Display only the city/sub-region part for readability
        display = tz.replace("_", " ").split("/", 1)[-1]
        buttons.append(
            InlineKeyboardButton(
                text=display,
                callback_data=f"{_CB_CITY}{tz}",
            )
        )
    rows = [buttons[i : i + _BUTTONS_PER_ROW] for i in range(0, len(buttons), _BUTTONS_PER_ROW)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


class TimezoneSetupStates(StatesGroup):
    """FSM states for the timezone picker."""

    selecting_continent = State()
    selecting_city = State()


def create_router() -> Router:
    """Create and return the timezone_setup FSM router."""
    router = Router(name="timezone_setup")

    @router.message(Command("timezone"))
    async def cmd_timezone(message: Message, state: FSMContext) -> None:
        """Enter the timezone picker FSM at the continent-selection step."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        await state.set_state(TimezoneSetupStates.selecting_continent)
        await message.answer(
            t("tz_pick_continent", lang),
            reply_markup=_continent_keyboard(lang),
        )

    @router.callback_query(
        StateFilter(TimezoneSetupStates.selecting_continent),
        F.data.startswith(_CB_CONTINENT),
    )
    async def cb_continent_selected(callback: CallbackQuery, state: FSMContext) -> None:
        """Handle continent button press — move to city selection."""
        await callback.answer()
        if callback.message is None or callback.from_user is None or callback.data is None:
            return
        lang = DEFAULT_LANGUAGE
        continent = callback.data[len(_CB_CONTINENT) :]
        if continent not in _TZ_MAP or not _TZ_MAP[continent]:
            # Unknown continent — restart
            await state.set_state(TimezoneSetupStates.selecting_continent)
            await callback.message.edit_text(
                t("tz_invalid", lang),
                reply_markup=_continent_keyboard(lang),
            )
            return
        await state.update_data(continent=continent)
        await state.set_state(TimezoneSetupStates.selecting_city)
        await callback.message.edit_text(
            t("tz_pick_city", lang),
            reply_markup=_city_keyboard(continent),
        )

    @router.callback_query(
        StateFilter(TimezoneSetupStates.selecting_city),
        F.data.startswith(_CB_CITY),
    )
    async def cb_city_selected(
        callback: CallbackQuery,
        state: FSMContext,
        timezone_service: TimezoneService,
    ) -> None:
        """Handle city button press — persist the timezone and clear FSM state."""
        await callback.answer()
        if callback.message is None or callback.from_user is None or callback.data is None:
            return
        lang = DEFAULT_LANGUAGE
        tz_string = callback.data[len(_CB_CITY) :]

        try:
            await timezone_service.set_timezone(callback.from_user.id, tz_string)
        except TimezoneError:
            logger.exception(
                "cb_city_selected: failed to set timezone %r for user %s",
                tz_string,
                callback.from_user.id,
            )
            # Return to continent selection on error
            await state.set_state(TimezoneSetupStates.selecting_continent)
            await callback.message.edit_text(
                t("tz_set_error", lang),
            )
            return
        except Exception:
            logger.exception(
                "cb_city_selected: unexpected error setting timezone %r for user %s",
                tz_string,
                callback.from_user.id,
            )
            await state.set_state(TimezoneSetupStates.selecting_continent)
            await callback.message.edit_text(t("tz_set_error", lang))
            return

        await state.clear()
        await callback.message.edit_text(
            t("tz_set_ok", lang).format(tz=tz_string),
        )
        logger.info(
            "cb_city_selected: user %s set timezone to %r",
            callback.from_user.id,
            tz_string,
        )

    return router
