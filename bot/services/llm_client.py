"""Thin Anthropic wrapper that captures token usage for cost tracking (AC-16)."""

import logging

import anthropic

from bot.config import Config

logger = logging.getLogger(__name__)


class LlmClient:
    """Async wrapper around the Anthropic Messages API.

    Returns (text, usage) so callers can record API usage via UsageService.
    """

    def __init__(self, config: Config) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        self._model = config.llm_model

    @property
    def model(self) -> str:
        """Return the pinned model identifier."""
        return self._model

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 220,
    ) -> tuple[str, anthropic.types.Usage]:
        """Send a single-turn completion and return (text, usage).

        *usage* carries input_tokens and output_tokens for the caller to record.
        """
        logger.debug("complete: model=%s, max_tokens=%d", self._model, max_tokens)

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        text: str = message.content[0].text  # type: ignore[union-attr]
        logger.debug(
            "complete: %d input + %d output tokens",
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        return text, message.usage
