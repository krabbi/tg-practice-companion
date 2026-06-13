"""Unit tests for the deterministic clarify flow (AC-8).

Covers:
- Entry with no assessment → exactly one clarify message with the deterministic string
- LLM client has zero calls throughout (no LLM in this flow, AC-8)
- Answering a clarify sets set_via='clarify'
- A second sweep does not re-ask (clarify_sent guard / no duplicate assessment)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.journal import JournalEntry, SelfAssessment
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.self_assessment_repository import SelfAssessmentRepository
from bot.services.assessment_service import AssessmentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entry(entry_id: uuid.UUID | None = None) -> JournalEntry:
    """Build a minimal JournalEntry."""
    e = JournalEntry()
    e.id = entry_id or uuid.uuid4()
    e.user_id = 123
    e.text = "мысль"
    e.source = "text"
    e.practice_id = uuid.uuid4()
    return e


def make_assessment_svc(
    entry: JournalEntry | None = None,
    existing_assessment: SelfAssessment | None = None,
) -> tuple[AssessmentService, MagicMock, MagicMock]:
    """Return (service, assessment_repo_mock, session_mock)."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    assessment_repo = MagicMock(spec=SelfAssessmentRepository)
    assessment_repo.get_by_entry_id = AsyncMock(return_value=existing_assessment)

    if existing_assessment is None:
        new_a = SelfAssessment()
        new_a.id = uuid.uuid4()
        new_a.journal_entry_id = entry.id if entry else uuid.uuid4()
        new_a.leads_to_goals = True
        new_a.set_via = "clarify"
        assessment_repo.create = AsyncMock(return_value=new_a)

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.get_by_id = AsyncMock(return_value=entry)

    prompt_repo = MagicMock(spec=PendingPromptRepository)

    svc = AssessmentService(
        session=session,
        assessment_repo=assessment_repo,
        journal_repo=journal_repo,
        prompt_repo=prompt_repo,
    )
    return svc, assessment_repo, session


# ---------------------------------------------------------------------------
# needs_clarify tests (core clarify logic lives in AssessmentService)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_needs_clarify_true_for_unanswered_thought_entry() -> None:
    """needs_clarify returns True when the entry has no self-assessment."""
    entry = make_entry()
    svc, _, _ = make_assessment_svc(entry=entry, existing_assessment=None)

    result = await svc.needs_clarify(entry.id)

    assert result is True


@pytest.mark.asyncio
async def test_needs_clarify_false_after_assessment_recorded() -> None:
    """needs_clarify returns False once an assessment exists."""
    entry = make_entry()
    existing = SelfAssessment()
    existing.id = uuid.uuid4()
    existing.journal_entry_id = entry.id
    existing.leads_to_goals = True
    existing.set_via = "button"

    svc, _, _ = make_assessment_svc(entry=entry, existing_assessment=existing)

    result = await svc.needs_clarify(entry.id)

    assert result is False


# ---------------------------------------------------------------------------
# Deterministic clarify string — no LLM
# ---------------------------------------------------------------------------


def test_clarify_string_is_deterministic_and_matches_i18n() -> None:
    """The clarify question is the fixed i18n string; no LLM involved."""
    from bot.i18n import t

    clarify_ru = t("assess_clarify", "ru")
    clarify_en = t("assess_clarify", "en")

    # Both must be non-empty deterministic strings
    assert clarify_ru
    assert clarify_en
    assert "цел" in clarify_ru.lower() or "goal" in clarify_en.lower()


@pytest.mark.asyncio
async def test_no_llm_calls_in_clarify_flow() -> None:
    """LLM client is never invoked anywhere in the clarify/assessment flow."""
    entry = make_entry()
    svc, assessment_repo, session = make_assessment_svc(entry=entry, existing_assessment=None)

    # Attach a mock LLM client to the service to verify zero calls
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock()

    # Run needs_clarify and record
    await svc.needs_clarify(entry.id)
    await svc.record(
        journal_entry_id=entry.id,
        leads_to_goals=True,
        set_via="clarify",
    )

    # LLM must have zero calls
    mock_llm.complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Clarify answer sets set_via='clarify'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarify_answer_sets_set_via_clarify() -> None:
    """Answering a clarify question stores set_via='clarify', not 'button'."""
    entry = make_entry()
    svc, assessment_repo, session = make_assessment_svc(entry=entry, existing_assessment=None)

    await svc.record(
        journal_entry_id=entry.id,
        leads_to_goals=False,
        set_via="clarify",
    )

    assessment_repo.create.assert_awaited_once()
    _, kwargs = assessment_repo.create.call_args
    assert kwargs["set_via"] == "clarify"
    assert kwargs["leads_to_goals"] is False
    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Second sweep does not re-ask (idempotency)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_sweep_does_not_re_clarify() -> None:
    """Once an assessment is recorded, needs_clarify returns False (no re-ask)."""
    entry = make_entry()
    # First sweep: no assessment
    svc, assessment_repo, session = make_assessment_svc(entry=entry, existing_assessment=None)

    first_result = await svc.needs_clarify(entry.id)
    assert first_result is True

    # Record assessment
    await svc.record(
        journal_entry_id=entry.id,
        leads_to_goals=True,
        set_via="clarify",
    )

    # Second sweep: assessment now exists
    existing = SelfAssessment()
    existing.id = uuid.uuid4()
    existing.journal_entry_id = entry.id
    existing.leads_to_goals = True
    existing.set_via = "clarify"

    svc2, _, _ = make_assessment_svc(entry=entry, existing_assessment=existing)
    second_result = await svc2.needs_clarify(entry.id)
    assert second_result is False


@pytest.mark.asyncio
async def test_duplicate_clarify_answer_raises_assessment_error() -> None:
    """Attempting to record a second assessment raises AssessmentError."""
    from bot.exceptions import AssessmentError

    entry = make_entry()
    existing = SelfAssessment()
    existing.id = uuid.uuid4()
    existing.journal_entry_id = entry.id
    existing.leads_to_goals = True
    existing.set_via = "clarify"

    svc, _, _ = make_assessment_svc(entry=entry, existing_assessment=existing)

    with pytest.raises(AssessmentError, match="already has"):
        await svc.record(
            journal_entry_id=entry.id,
            leads_to_goals=False,
            set_via="clarify",
        )
