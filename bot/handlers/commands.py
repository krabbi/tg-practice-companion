"""Core bot commands: /start and /help."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.timezone_setup import (
    TimezoneSetupStates,
    continent_keyboard,
)
from bot.i18n import DEFAULT_LANGUAGE, t
from bot.repositories.user_repository import UserRepository


def create_router() -> Router:
    """Create and return a fresh commands Router with all handlers registered.

    Using a factory instead of a module-level singleton prevents the
    'Router is already attached' error when create_dispatcher is called
    more than once in the same process (e.g. in tests).
    """
    router = Router(name="commands")

    @router.message(Command("start"))
    async def cmd_start(
        message: Message,
        state: FSMContext,
        user_repo: UserRepository,
    ) -> None:
        """Greet the user; on first run (timezone unset) enter the timezone picker."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        user = await user_repo.get_by_telegram_id(message.from_user.id)
        if user is not None and user.timezone is None:
            # First-run: redirect into the timezone picker before the welcome message.
            await state.set_state(TimezoneSetupStates.selecting_continent)
            await message.answer(
                t("tz_pick_continent", lang),
                reply_markup=continent_keyboard(lang),
            )
            return
        await message.answer(t("start_welcome", lang))

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        """Show the list of available commands."""
        lang = DEFAULT_LANGUAGE
        await message.answer(t("help_text", lang))

    return router


# Module-level router for convenience when a single instance is sufficient.
# Production code uses create_router() via create_dispatcher(); this alias
# exists for external references that expect commands.router.
router = create_router()
