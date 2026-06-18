"""Unit tests for AssessmentService and assessment handler (AC-8 buttons)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.exceptions import AssessmentError
from bot.models.journal import JournalEntry, SelfAssessment
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.self_assessment_repository import SelfAssessmentRepository
from bot.services.assessment_service import AssessmentResult, AssessmentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entry(entry_id: uuid.UUID | None = None) -> JournalEntry:
    """Build a minimal JournalEntry."""
    e = JournalEntry()
    e.id = entry_id or uuid.uuid4()
    e.user_id = 123
    e.text = "thought text"
    e.source = "text"
    e.practice_id = uuid.uuid4()
    return e


def make_assessment(
    entry_id: uuid.UUID, leads_to_goals: bool = True, set_via: str = "button"
) -> SelfAssessment:
    """Build a minimal SelfAssessment."""
    a = SelfAssessment()
    a.id = uuid.uuid4()
    a.journal_entry_id = entry_id
    a.leads_to_goals = leads_to_goals
    a.set_via = set_via
    return a


def make_service(
    entry: JournalEntry | None = None,
    existing_assessment: SelfAssessment | None = None,
    new_assessment: SelfAssessment | None = None,
) -> tuple[AssessmentService, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Build AssessmentService with mocked repos."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    assessment_repo = MagicMock(spec=SelfAssessmentRepository)
    assessment_repo.get_by_entry_id = AsyncMock(return_value=existing_assessment)
    if new_assessment is not None:
        assessment_repo.create = AsyncMock(return_value=new_assessment)
    else:
        # default: return a new assessment
        _entry_id = entry.id if entry else uuid.uuid4()
        assessment_repo.create = AsyncMock(return_value=make_assessment(_entry_id))

    journal_repo = MagicMock(spec=JournalRepository)
    journal_repo.get_by_id = AsyncMock(return_value=entry)

    prompt_repo = MagicMock(spec=PendingPromptRepository)

    svc = AssessmentService(
        session=session,
        assessment_repo=assessment_repo,
        journal_repo=journal_repo,
        prompt_repo=prompt_repo,
    )
    return svc, assessment_repo, journal_repo, prompt_repo, session


# ---------------------------------------------------------------------------
# AssessmentService.record tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_yes_stores_leads_to_goals_true_via_button() -> None:
    """assess:...:yes writes leads_to_goals=True, set_via=button."""
    entry = make_entry()
    new_a = make_assessment(entry.id, leads_to_goals=True, set_via="button")
    svc, assessment_repo, _, _, session = make_service(entry=entry, new_assessment=new_a)

    result = await svc.record(
        user_id=123, journal_entry_id=entry.id, leads_to_goals=True, set_via="button"
    )

    assessment_repo.create.assert_awaited_once_with(
        journal_entry_id=entry.id, leads_to_goals=True, set_via="button"
    )
    session.commit.assert_awaited_once()
    assert isinstance(result, AssessmentResult)
    assert result.leads_to_goals is True
    assert result.set_via == "button"


@pytest.mark.asyncio
async def test_record_no_stores_leads_to_goals_false_via_button() -> None:
    """assess:...:no writes leads_to_goals=False, set_via=button."""
    entry = make_entry()
    new_a = make_assessment(entry.id, leads_to_goals=False, set_via="button")
    svc, assessment_repo, _, _, session = make_service(entry=entry, new_assessment=new_a)

    result = await svc.record(
        user_id=123, journal_entry_id=entry.id, leads_to_goals=False, set_via="button"
    )

    _, kwargs = assessment_repo.create.call_args
    assert kwargs["leads_to_goals"] is False
    assert kwargs["set_via"] == "button"
    assert result.leads_to_goals is False


@pytest.mark.asyncio
async def test_record_raises_when_entry_not_found() -> None:
    """AssessmentError is raised if the journal entry does not exist."""
    svc, _, _, _, _ = make_service(entry=None)

    with pytest.raises(AssessmentError, match="not found"):
        await svc.record(
            user_id=123, journal_entry_id=uuid.uuid4(), leads_to_goals=True, set_via="button"
        )


@pytest.mark.asyncio
async def test_record_raises_when_assessment_already_exists() -> None:
    """AssessmentError raised when the entry already has a self-assessment."""
    entry = make_entry()
    existing = make_assessment(entry.id)
    svc, _, _, _, _ = make_service(entry=entry, existing_assessment=existing)

    with pytest.raises(AssessmentError, match="already has"):
        await svc.record(
            user_id=123, journal_entry_id=entry.id, leads_to_goals=True, set_via="button"
        )


@pytest.mark.asyncio
async def test_record_does_not_commit_on_error() -> None:
    """Session.commit is NOT called when AssessmentError is raised."""
    svc, _, _, _, session = make_service(entry=None)

    with pytest.raises(AssessmentError):
        await svc.record(
            user_id=123, journal_entry_id=uuid.uuid4(), leads_to_goals=True, set_via="button"
        )

    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# needs_clarify tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_needs_clarify_true_when_no_assessment() -> None:
    """needs_clarify returns True when entry exists but has no assessment."""
    entry = make_entry()
    svc, assessment_repo, _, _, _ = make_service(entry=entry, existing_assessment=None)

    result = await svc.needs_clarify(entry.id, 123)

    assert result is True


@pytest.mark.asyncio
async def test_needs_clarify_false_when_assessment_exists() -> None:
    """needs_clarify returns False when entry already has an assessment."""
    entry = make_entry()
    existing = make_assessment(entry.id)
    svc, _, _, _, _ = make_service(entry=entry, existing_assessment=existing)

    result = await svc.needs_clarify(entry.id, 123)

    assert result is False


@pytest.mark.asyncio
async def test_needs_clarify_false_when_entry_not_found() -> None:
    """needs_clarify returns False when the journal entry does not exist."""
    svc, _, _, _, _ = make_service(entry=None)

    result = await svc.needs_clarify(uuid.uuid4(), 123)

    assert result is False


# ---------------------------------------------------------------------------
# Assessment handler callback parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assessment_handler_callback_yes() -> None:
    """cb_assess: 'assess:<id>:yes' records assessment with leads_to_goals=True."""
    from aiogram.types import CallbackQuery, Message, User

    entry = make_entry()
    new_a = make_assessment(entry.id, leads_to_goals=True, set_via="button")
    svc, assessment_repo, journal_repo, _, session = make_service(entry=entry, new_assessment=new_a)

    # Build the router and get the handler
    from bot.handlers.assessment import create_router

    router = create_router()

    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.data = f"assess:{entry.id}:yes"
    user = MagicMock(spec=User)
    user.id = 123
    callback.from_user = user
    msg = MagicMock(spec=Message)
    msg.edit_reply_markup = AsyncMock()
    callback.message = msg

    # Call the handler directly using the inner function
    # Find the callback handler registered on the router
    handlers = router.callback_query.handlers
    assert len(handlers) > 0

    # Invoke via the router's observers
    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    assessment_repo.create.assert_awaited_once()
    _, kwargs = assessment_repo.create.call_args
    assert kwargs["leads_to_goals"] is True
    assert kwargs["set_via"] == "button"
    msg.edit_reply_markup.assert_awaited_once_with(reply_markup=None)


@pytest.mark.asyncio
async def test_assessment_handler_callback_no() -> None:
    """cb_assess: 'assess:<id>:no' records assessment with leads_to_goals=False."""
    from aiogram.types import CallbackQuery, Message, User

    entry = make_entry()
    new_a = make_assessment(entry.id, leads_to_goals=False, set_via="button")
    svc, assessment_repo, _, _, _ = make_service(entry=entry, new_assessment=new_a)

    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.data = f"assess:{entry.id}:no"
    user = MagicMock(spec=User)
    user.id = 123
    callback.from_user = user
    msg = MagicMock(spec=Message)
    msg.edit_reply_markup = AsyncMock()
    callback.message = msg

    from bot.handlers.assessment import create_router

    router = create_router()
    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    _, kwargs = assessment_repo.create.call_args
    assert kwargs["leads_to_goals"] is False
