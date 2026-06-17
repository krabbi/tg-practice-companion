"""Handler for the /admin command — opens the web admin Mini App (AC-19)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.config import Config
from bot.i18n import DEFAULT_LANGUAGE, t


def create_router(config: Config) -> Router:
    """Create and return the admin router with the config bound at construction time."""
    router = Router(name="admin")

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        """Reply with a Web App button to open the admin panel, or an error if unconfigured."""
        lang = DEFAULT_LANGUAGE
        if not config.web_app_url:
            await message.answer(t("admin_not_configured", lang))
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("admin_open_button", lang),
                        web_app=WebAppInfo(url=config.web_app_url),
                    )
                ]
            ]
        )
        await message.answer(t("admin_open_button", lang), reply_markup=keyboard)

    return router
