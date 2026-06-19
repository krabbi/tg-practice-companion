"""Service for delivering a practice to the user via the Telegram bot."""

import logging

from aiogram import Bot

from bot.exceptions import DeliveryError, MediaAssetError
from bot.models.practice import Practice
from bot.repositories.pending_prompt_repository import PendingPromptRepository

logger = logging.getLogger(__name__)

# Maps practice name suffixes / content_type to prompt kind.
# For question practices with no special kind hint, default to "thought".
_DEFAULT_PROMPT_KIND = "thought"


class DeliveryService:
    """Renders and sends a practice to the user through the Telegram Bot API.

    When *prompt_repo* is provided, every outgoing `question` practice writes a
    `pending_prompt` row capturing the returned Telegram message_id (Decision B1).
    The scheduler passes *prompt_repo* so journal capture can bind replies precisely.

    Wraps every send in try/except — a bad file_id must be logged and visible,
    never swallowed silently (per coding-patterns.md error handling rule).
    """

    def __init__(
        self,
        bot: Bot,
        prompt_repo: PendingPromptRepository | None = None,
    ) -> None:
        self._bot = bot
        self._prompt_repo = prompt_repo

    async def send(self, practice: Practice, user_id: int) -> None:
        """Deliver *practice* to *user_id* via the appropriate Telegram send method.

        For `question` practices, writes a `pending_prompt` row with the outgoing
        message_id when *prompt_repo* is available.

        Raises DeliveryError on failure after logging the error.
        """
        try:
            await self._dispatch(practice, user_id)
        except DeliveryError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to deliver practice %s (%r) to user %s: %s",
                practice.id,
                practice.name,
                user_id,
                exc,
                exc_info=True,
            )
            raise DeliveryError(f"Delivery failed for practice {practice.id}: {exc}") from exc

    async def _dispatch(self, practice: Practice, user_id: int) -> None:
        """Route to the correct Telegram send method based on content_type."""
        if practice.content_type == "question":
            text = practice.content or ""
            sent = await self._bot.send_message(chat_id=user_id, text=text)
            # Write a pending_prompt so the user's reply can be bound to this practice
            if self._prompt_repo is not None:
                await self._prompt_repo.create(
                    user_id=user_id,
                    kind=_DEFAULT_PROMPT_KIND,
                    practice_id=practice.id,
                    telegram_message_id=sent.message_id,
                )

        elif practice.content_type == "text":
            text = practice.content or ""
            await self._bot.send_message(chat_id=user_id, text=text)

        elif practice.content_type == "audio":
            file_id = self._resolve_telegram_file_id(practice)
            await self._bot.send_audio(chat_id=user_id, audio=file_id)

        elif practice.content_type == "image":
            file_id = self._resolve_telegram_file_id(practice)
            await self._bot.send_photo(chat_id=user_id, photo=file_id)

        elif practice.content_type == "video":
            file_id = self._resolve_telegram_file_id(practice)
            await self._bot.send_video(chat_id=user_id, video=file_id)

        else:
            raise DeliveryError(f"Unknown content_type {practice.content_type!r}")

    @staticmethod
    def _resolve_telegram_file_id(practice: Practice) -> str:
        """Return the stored telegram_file_id from the practice's media_asset.

        Raises MediaAssetError if the asset is missing or has no file_id.
        """
        asset = practice.media_asset
        if asset is None:
            raise MediaAssetError(f"Practice {practice.id} ({practice.name!r}) has no media_asset")
        if not asset.telegram_file_id:
            raise MediaAssetError(
                f"MediaAsset {asset.id} for practice {practice.name!r} has no telegram_file_id"
            )
        # Return file_id unchanged — AC-2 requires the stored ID to be used as-is
        return asset.telegram_file_id
