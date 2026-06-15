"""Handlers for /want and /wants commands (AC-9)."""

import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.i18n import DEFAULT_LANGUAGE, t
from bot.services.want_list_service import WantListService

logger = logging.getLogger(__name__)


def create_router() -> Router:
    """Create and return the want_list router."""
    router = Router(name="want_list")

    @router.message(Command("want"))
    async def cmd_want(
        message: Message,
        want_list_service: WantListService,
    ) -> None:
        """Add a new item to the want list via /want <text>."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        raw = message.text or ""
        parts = raw.split(maxsplit=1)
        item_text = parts[1].strip() if len(parts) > 1 else ""
        if not item_text:
            await message.answer(t("want_no_text", lang))
            return
        try:
            await want_list_service.add(message.from_user.id, item_text)
            await message.answer(t("want_added", lang))
        except Exception:
            logger.exception("cmd_want: failed to add item for user %s", message.from_user.id)
            await message.answer(t("want_add_failed", lang))

    @router.message(Command("wants"))
    async def cmd_wants(
        message: Message,
        want_list_service: WantListService,
    ) -> None:
        """List all undone want-list items for the user."""
        if message.from_user is None:
            return
        lang = DEFAULT_LANGUAGE
        try:
            items = await want_list_service.list_active(message.from_user.id)
            if not items:
                await message.answer(t("wants_empty", lang))
                return
            lines = [t("wants_list_header", lang)]
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {escape(item.text)}")
            await message.answer("\n".join(lines))
        except Exception:
            logger.exception("cmd_wants: failed to list items for user %s", message.from_user.id)
            await message.answer(t("want_list_error", lang))

    return router
