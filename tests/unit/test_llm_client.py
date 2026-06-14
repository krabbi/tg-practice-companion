"""Unit tests for LlmClient — mocks the Anthropic API."""

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from bot.config import Config
from bot.services.llm_client import LlmClient


@pytest.fixture
def llm_client(fake_config: Config) -> LlmClient:
    """Return an LlmClient backed by the fake config."""
    return LlmClient(fake_config)


def test_model_property(llm_client: LlmClient, fake_config: Config) -> None:
    """model property returns the config's llm_model."""
    assert llm_client.model == fake_config.llm_model


@pytest.mark.asyncio
async def test_complete_returns_text_and_usage(llm_client: LlmClient, fake_config: Config) -> None:
    """complete() returns the response text and the Usage object from the API."""
    fake_usage = anthropic.types.Usage(input_tokens=42, output_tokens=17)
    fake_content = MagicMock()
    fake_content.text = "Hello, analysis!"
    fake_message = MagicMock()
    fake_message.content = [fake_content]
    fake_message.usage = fake_usage

    with patch.object(
        llm_client._client.messages,
        "create",
        new=AsyncMock(return_value=fake_message),
    ) as mock_create:
        text, usage = await llm_client.complete(
            system="You are helpful.",
            user="Summarise my week.",
            max_tokens=220,
        )

    assert text == "Hello, analysis!"
    assert usage.input_tokens == 42
    assert usage.output_tokens == 17
    mock_create.assert_awaited_once_with(
        model=fake_config.llm_model,
        max_tokens=220,
        system="You are helpful.",
        messages=[{"role": "user", "content": "Summarise my week."}],
    )


@pytest.mark.asyncio
async def test_complete_uses_default_max_tokens(
    llm_client: LlmClient,
) -> None:
    """complete() defaults to max_tokens=220 when not specified."""
    fake_usage = anthropic.types.Usage(input_tokens=10, output_tokens=5)
    fake_content = MagicMock()
    fake_content.text = "ok"
    fake_message = MagicMock()
    fake_message.content = [fake_content]
    fake_message.usage = fake_usage

    with patch.object(
        llm_client._client.messages,
        "create",
        new=AsyncMock(return_value=fake_message),
    ) as mock_create:
        await llm_client.complete(system="sys", user="user")

    assert mock_create.call_args.kwargs["max_tokens"] == 220
