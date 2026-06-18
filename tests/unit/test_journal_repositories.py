"""Unit tests for journal repositories using in-memory SQLite (db_session fixture).

Tests cover:
- PendingPromptRepository: create, get_by_telegram_message_id, newest_unconsumed, mark_consumed, mark_clarify_sent
- JournalRepository: create, get_by_id
- SelfAssessmentRepository: create, get_by_entry_id
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.self_assessment_repository import SelfAssessmentRepository

# ---------------------------------------------------------------------------
# PendingPromptRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_prompt_create_and_fetch(db_session: AsyncSession) -> None:
    """create() persists a pending prompt and it can be retrieved."""
    repo = PendingPromptRepository(db_session)
    practice_id = uuid.uuid4()

    prompt = await repo.create(
        user_id=111,
        kind="thought",
        practice_id=practice_id,
        telegram_message_id=42,
    )
    await db_session.commit()

    # Fetch via get_by_telegram_message_id
    fetched = await repo.get_by_telegram_message_id(111, 42)
    assert fetched is not None
    assert fetched.id == prompt.id
    assert fetched.kind == "thought"
    assert fetched.practice_id == practice_id
    assert fetched.consumed is False
    assert fetched.clarify_sent is False


@pytest.mark.asyncio
async def test_pending_prompt_get_by_telegram_message_id_returns_none_for_unknown(
    db_session: AsyncSession,
) -> None:
    """get_by_telegram_message_id returns None when no match exists."""
    repo = PendingPromptRepository(db_session)
    result = await repo.get_by_telegram_message_id(999, 9999)
    assert result is None


@pytest.mark.asyncio
async def test_pending_prompt_get_by_telegram_message_id_ignores_consumed(
    db_session: AsyncSession,
) -> None:
    """get_by_telegram_message_id returns None for consumed prompts."""
    repo = PendingPromptRepository(db_session)
    prompt = await repo.create(user_id=111, kind="thought", telegram_message_id=77)
    await db_session.commit()

    await repo.mark_consumed(prompt.id)
    await db_session.commit()

    result = await repo.get_by_telegram_message_id(111, 77)
    assert result is None


@pytest.mark.asyncio
async def test_pending_prompt_newest_unconsumed_returns_latest(db_session: AsyncSession) -> None:
    """newest_unconsumed returns the most recently created unconsumed prompt."""
    repo = PendingPromptRepository(db_session)

    await repo.create(user_id=222, kind="thought")
    await db_session.commit()
    p2 = await repo.create(user_id=222, kind="other")
    await db_session.commit()

    result = await repo.newest_unconsumed(222)
    assert result is not None
    assert result.id == p2.id


@pytest.mark.asyncio
async def test_pending_prompt_newest_unconsumed_with_not_before_cutoff(
    db_session: AsyncSession,
) -> None:
    """newest_unconsumed excludes prompts older than not_before."""
    repo = PendingPromptRepository(db_session)

    # Create a prompt; it will be excluded because we pass a future cutoff
    await repo.create(user_id=333, kind="thought")
    await db_session.commit()

    # Use a not_before in the future so the prompt is excluded
    future_cutoff = datetime.now(UTC) + timedelta(hours=1)
    result = await repo.newest_unconsumed(333, not_before=future_cutoff)
    assert result is None


@pytest.mark.asyncio
async def test_pending_prompt_newest_unconsumed_with_not_before_includes_recent(
    db_session: AsyncSession,
) -> None:
    """newest_unconsumed includes prompts created after not_before."""
    repo = PendingPromptRepository(db_session)
    past_cutoff = datetime.now(UTC) - timedelta(hours=1)

    prompt = await repo.create(user_id=444, kind="thought")
    await db_session.commit()

    result = await repo.newest_unconsumed(444, not_before=past_cutoff)
    assert result is not None
    assert result.id == prompt.id


@pytest.mark.asyncio
async def test_pending_prompt_mark_consumed(db_session: AsyncSession) -> None:
    """mark_consumed sets consumed=True on the prompt."""
    repo = PendingPromptRepository(db_session)
    prompt = await repo.create(user_id=555, kind="thought")
    await db_session.commit()

    await repo.mark_consumed(prompt.id)
    await db_session.commit()

    # Expire and re-fetch
    db_session.expire_all()
    result = await repo.newest_unconsumed(555)
    assert result is None  # consumed prompt is excluded


@pytest.mark.asyncio
async def test_pending_prompt_mark_clarify_sent(db_session: AsyncSession) -> None:
    """mark_clarify_sent sets clarify_sent=True on the prompt."""
    from sqlalchemy import select

    from bot.models.journal import PendingPrompt as PP

    repo = PendingPromptRepository(db_session)
    prompt = await repo.create(user_id=666, kind="thought")
    await db_session.commit()

    await repo.mark_clarify_sent(prompt.id)
    await db_session.commit()

    # Re-fetch using async select to verify the update
    row = (await db_session.execute(select(PP).where(PP.id == prompt.id))).scalar_one_or_none()
    assert row is not None
    assert row.clarify_sent is True


# ---------------------------------------------------------------------------
# JournalRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_journal_repository_create_and_get(db_session: AsyncSession) -> None:
    """JournalRepository.create persists an entry; get_by_id retrieves it."""
    repo = JournalRepository(db_session)
    practice_id = uuid.uuid4()

    entry = await repo.create(
        user_id=111,
        text="мысль",
        source="text",
        practice_id=practice_id,
    )
    await db_session.commit()

    fetched = await repo.get_by_id(entry.id, 111)
    assert fetched is not None
    assert fetched.text == "мысль"
    assert fetched.source == "text"
    assert fetched.user_id == 111
    assert fetched.practice_id == practice_id


@pytest.mark.asyncio
async def test_journal_repository_create_voice_entry(db_session: AsyncSession) -> None:
    """JournalRepository.create works with source='voice' and no practice_id."""
    repo = JournalRepository(db_session)

    entry = await repo.create(
        user_id=222,
        text="голосовой текст",
        source="voice",
        practice_id=None,
    )
    await db_session.commit()

    fetched = await repo.get_by_id(entry.id, 222)
    assert fetched is not None
    assert fetched.source == "voice"
    assert fetched.practice_id is None


@pytest.mark.asyncio
async def test_journal_repository_get_by_id_returns_none_for_unknown(
    db_session: AsyncSession,
) -> None:
    """get_by_id returns None for a non-existent entry."""
    repo = JournalRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4(), 111)
    assert result is None


# ---------------------------------------------------------------------------
# SelfAssessmentRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_assessment_create_and_fetch(db_session: AsyncSession) -> None:
    """SelfAssessmentRepository.create persists an assessment; get_by_entry_id retrieves it."""
    journal_repo = JournalRepository(db_session)
    assessment_repo = SelfAssessmentRepository(db_session)

    entry = await journal_repo.create(user_id=111, text="мысль", source="text", practice_id=None)
    await db_session.commit()

    assessment = await assessment_repo.create(
        journal_entry_id=entry.id,
        leads_to_goals=True,
        set_via="button",
    )
    await db_session.commit()

    fetched = await assessment_repo.get_by_entry_id(entry.id, 111)
    assert fetched is not None
    assert fetched.id == assessment.id
    assert fetched.leads_to_goals is True
    assert fetched.set_via == "button"


@pytest.mark.asyncio
async def test_self_assessment_get_by_entry_id_returns_none_when_absent(
    db_session: AsyncSession,
) -> None:
    """get_by_entry_id returns None when no assessment exists for the entry."""
    assessment_repo = SelfAssessmentRepository(db_session)
    result = await assessment_repo.get_by_entry_id(uuid.uuid4(), 111)
    assert result is None


@pytest.mark.asyncio
async def test_self_assessment_clarify_set_via(db_session: AsyncSession) -> None:
    """Self-assessment with set_via='clarify' is stored correctly."""
    journal_repo = JournalRepository(db_session)
    assessment_repo = SelfAssessmentRepository(db_session)

    entry = await journal_repo.create(user_id=222, text="мысль", source="text", practice_id=None)
    await db_session.commit()

    await assessment_repo.create(
        journal_entry_id=entry.id,
        leads_to_goals=False,
        set_via="clarify",
    )
    await db_session.commit()

    fetched = await assessment_repo.get_by_entry_id(entry.id, 222)
    assert fetched is not None
    assert fetched.set_via == "clarify"
    assert fetched.leads_to_goals is False
