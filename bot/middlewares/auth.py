"""Authentication middleware — single-ID whitelist (AC-1)."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Drop updates from any Telegram user not in the allowed-IDs whitelist."""

    def __init__(self, allowed_user_ids: list[int]) -> None:
        self._allowed: frozenset[int] = frozenset(allowed_user_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Pass the update through only if the sender is whitelisted."""
        update: Update | None = data.get("event_update")
        user = data.get("event_from_user")

        if user is None:
            # Anonymous update (channel post, etc.) — drop silently
            if update is not None:
                logger.debug("Dropping anonymous update %s", update.update_id)
            return None

        if user.id not in self._allowed:
            logger.warning("Dropping update from unauthorized user %s", user.id)
            return None

        return await handler(event, data)
