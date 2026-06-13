"""Core bot commands: /start and /help."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.i18n import DEFAULT_LANGUAGE, t


def create_router() -> Router:
    """Create and return a fresh commands Router with all handlers registered.

    Using a factory instead of a module-level singleton prevents the
    'Router is already attached' error when create_dispatcher is called
    more than once in the same process (e.g. in tests).
    """
    router = Router(name="commands")

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Greet the whitelisted user and confirm the bot is running."""
        lang = DEFAULT_LANGUAGE
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
