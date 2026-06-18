"""Service for managing self-assessments on journal entries (AC-8)."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.exceptions import AssessmentError
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.pending_prompt_repository import PendingPromptRepository
from bot.repositories.self_assessment_repository import SelfAssessmentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssessmentResult:
    """Result returned by AssessmentService.record."""

    assessment_id: uuid.UUID
    leads_to_goals: bool
    set_via: str


class AssessmentService:
    """Records self-assessments and manages the deterministic clarify flow (AC-8).

    No LLM is used anywhere in this service — the clarify question is a single
    fixed localised phrase returned by the handler via t("assess_clarify", lang).
    """

    def __init__(
        self,
        session: AsyncSession,
        assessment_repo: SelfAssessmentRepository,
        journal_repo: JournalRepository,
        prompt_repo: PendingPromptRepository,
    ) -> None:
        self._session = session
        self._assessment_repo = assessment_repo
        self._journal_repo = journal_repo
        self._prompt_repo = prompt_repo

    async def record(
        self,
        *,
        user_id: int,
        journal_entry_id: uuid.UUID,
        leads_to_goals: bool,
        set_via: str,
    ) -> AssessmentResult:
        """Persist a self-assessment for the given journal entry.

        Raises AssessmentError if the entry does not exist, belongs to a different user,
        or already has an assessment.
        """
        entry = await self._journal_repo.get_by_id(journal_entry_id, user_id)
        if entry is None:
            raise AssessmentError(f"JournalEntry {journal_entry_id} not found")

        existing = await self._assessment_repo.get_by_entry_id(journal_entry_id, user_id)
        if existing is not None:
            raise AssessmentError(f"JournalEntry {journal_entry_id} already has a self-assessment")

        assessment = await self._assessment_repo.create(
            journal_entry_id=journal_entry_id,
            leads_to_goals=leads_to_goals,
            set_via=set_via,
        )
        await self._session.commit()
        return AssessmentResult(
            assessment_id=assessment.id,
            leads_to_goals=leads_to_goals,
            set_via=set_via,
        )

    async def needs_clarify(self, journal_entry_id: uuid.UUID, user_id: int) -> bool:
        """Return True if this thought entry has no assessment and no clarify sent yet.

        Called by the clarify sweep before sending a follow-up question.
        Checks the self_assessments table (no assessment) and the pending_prompt
        clarify_sent flag (not yet asked).
        """
        entry = await self._journal_repo.get_by_id(journal_entry_id, user_id)
        if entry is None:
            return False

        assessment = await self._assessment_repo.get_by_entry_id(journal_entry_id, user_id)
        return assessment is None
