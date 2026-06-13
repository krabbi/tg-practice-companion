"""Unit tests for JournalService.capture (AC-6).

Covers:
- Text reply with no reply-to binds to the newest unconsumed prompt (AC-6)
- Reply-to message_id binds precisely even when another prompt is newer
- Stale prompts (older than expiry window) are ignored
- No prompt → entry stored with practice_id=None, needs_assessment=False
- Thought prompt → needs_assessment=True
- Non-thought prompt → needs_assessment=False
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, PendingPrompt
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.services.journal_service import _PROMPT_EXPIRY_HOURS, JournalService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_prompt(
    kind: str = "thought",
    practice_id: uuid.UUID | None = None,
    telegram_message_id: int | None = None,
    age_hours: float = 1.0,
) -> PendingPrompt:
    """Build a minimal PendingPrompt with controllable age."""
    p = PendingPrompt()
    p.id = uuid.uuid4()
    p.user_id = 123
    p.kind = kind
    p.practice_id = practice_id or uuid.uuid4()
    p.telegram_message_id = telegram_message_id
    p.consumed = False
    p.clarify_sent = False
    p.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    return p


def make_entry(practice_id: uuid.UUID | None = None) -> JournalEntry:
    """Build a minimal JournalEntry."""
    e = JournalEntry()
    e.id = uuid.uuid4()
    e.user_id = 123
    e.text = "test"
    e.source = "text"
    e.practice_id = practice_id
    e.created_at = datetime.now(UTC)
    return e


def make_service(
    prompt: PendingPrompt | None = None,
    entry: JournalEntry | None = None,
) -> tuple[JournalService, MagicMock, MagicMock, MagicMock]:
    """Build a JournalService with mocked repos and session."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.create = AsyncMock(return_value=entry or make_entry())

    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.get_by_telegram_message_id = AsyncMock(return_value=None)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=prompt)
    prompt_repo.mark_consumed = AsyncMock()

    svc = JournalService(session=session, journal_repo=journal_repo, prompt_repo=prompt_repo)
    return svc, journal_repo, prompt_repo, session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reply_to_binds_newest_unconsumed_prompt() -> None:
    """No reply-to → falls back to newest unconsumed prompt; entry bound to practice."""
    practice_id = uuid.uuid4()
    prompt = make_prompt(kind="thought", practice_id=practice_id)
    entry = make_entry(practice_id=practice_id)
    svc, journal_repo, prompt_repo, session = make_service(prompt=prompt, entry=entry)

    result = await svc.capture(user_id=123, text="мысль", source="text")

    prompt_repo.newest_unconsumed.assert_awaited_once()
    journal_repo.create.assert_awaited_once()
    _, kwargs = journal_repo.create.call_args
    assert kwargs["practice_id"] == practice_id
    prompt_repo.mark_consumed.assert_awaited_once_with(prompt.id)
    session.commit.assert_awaited_once()
    assert result.needs_assessment is True
    assert result.entry_id == entry.id
    assert result.prompt_id == prompt.id


@pytest.mark.asyncio
async def test_reply_to_binds_exact_prompt_even_when_another_is_newer() -> None:
    """reply_to_message_id exact match wins over the newest unconsumed prompt."""
    old_prompt = make_prompt(kind="thought", telegram_message_id=111, age_hours=5)
    new_prompt = make_prompt(kind="other", telegram_message_id=999, age_hours=0.1)
    entry = make_entry(practice_id=old_prompt.practice_id)

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.create = AsyncMock(return_value=entry)
    prompt_repo = MagicMock(spec=PendingPromptRepository)
    # Exact match returns old_prompt; newest_unconsumed would return new_prompt
    prompt_repo.get_by_telegram_message_id = AsyncMock(return_value=old_prompt)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=new_prompt)
    prompt_repo.mark_consumed = AsyncMock()

    svc = JournalService(session=session, journal_repo=journal_repo, prompt_repo=prompt_repo)
    result = await svc.capture(user_id=123, text="reply", source="text", reply_to_message_id=111)

    # Exact match should have been tried; newest_unconsumed must NOT have been called
    prompt_repo.get_by_telegram_message_id.assert_awaited_once_with(123, 111)
    prompt_repo.newest_unconsumed.assert_not_awaited()
    prompt_repo.mark_consumed.assert_awaited_once_with(old_prompt.id)
    assert result.prompt_id == old_prompt.id
    assert result.needs_assessment is True


@pytest.mark.asyncio
async def test_stale_prompt_is_not_bound() -> None:
    """Prompts older than _PROMPT_EXPIRY_HOURS are excluded; entry gets practice_id=None."""
    # newest_unconsumed with not_before will return None (stale prompt excluded in repo)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    journal_repo = MagicMock(spec=JournalRepository)
    entry = make_entry(practice_id=None)
    journal_repo.create = AsyncMock(return_value=entry)
    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.get_by_telegram_message_id = AsyncMock(return_value=None)
    # Simulate repo returning None (stale prompt filtered out at DB level)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=None)
    prompt_repo.mark_consumed = AsyncMock()

    svc = JournalService(session=session, journal_repo=journal_repo, prompt_repo=prompt_repo)
    result = await svc.capture(user_id=123, text="late reply", source="text")

    _, kwargs = journal_repo.create.call_args
    assert kwargs["practice_id"] is None
    prompt_repo.mark_consumed.assert_not_awaited()
    assert result.needs_assessment is False
    assert result.prompt_id is None


@pytest.mark.asyncio
async def test_no_prompt_at_all_stores_entry_without_practice() -> None:
    """When there is no pending prompt, the entry is stored with practice_id=None."""
    svc, journal_repo, prompt_repo, session = make_service(prompt=None)

    result = await svc.capture(user_id=123, text="random text", source="text")

    _, kwargs = journal_repo.create.call_args
    assert kwargs["practice_id"] is None
    assert result.needs_assessment is False
    assert result.prompt_id is None
    prompt_repo.mark_consumed.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_thought_prompt_does_not_need_assessment() -> None:
    """kind='other' → needs_assessment is False even when a prompt is bound."""
    prompt = make_prompt(kind="other")
    svc, _, _, _ = make_service(prompt=prompt)

    result = await svc.capture(user_id=123, text="text", source="text")

    assert result.needs_assessment is False


@pytest.mark.asyncio
async def test_newest_unconsumed_receives_not_before_cutoff() -> None:
    """newest_unconsumed is called with a not_before cutoff ~_PROMPT_EXPIRY_HOURS ago."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.create = AsyncMock(return_value=make_entry())
    prompt_repo = MagicMock(spec=PendingPromptRepository)
    prompt_repo.get_by_telegram_message_id = AsyncMock(return_value=None)
    prompt_repo.newest_unconsumed = AsyncMock(return_value=None)
    prompt_repo.mark_consumed = AsyncMock()

    svc = JournalService(session=session, journal_repo=journal_repo, prompt_repo=prompt_repo)

    fixed_now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
    with patch("bot.services.journal_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        await svc.capture(user_id=123, text="t", source="text")

    expected_cutoff = fixed_now - timedelta(hours=_PROMPT_EXPIRY_HOURS)
    prompt_repo.newest_unconsumed.assert_awaited_once_with(123, not_before=expected_cutoff)


@pytest.mark.asyncio
async def test_capture_creates_entry_with_correct_source() -> None:
    """source field is passed through correctly to the repository."""
    prompt = make_prompt(kind="thought")
    entry = make_entry()
    svc, journal_repo, _, _ = make_service(prompt=prompt, entry=entry)

    await svc.capture(user_id=123, text="голос", source="voice")

    _, kwargs = journal_repo.create.call_args
    assert kwargs["source"] == "voice"
    assert kwargs["text"] == "голос"
    assert kwargs["user_id"] == 123
