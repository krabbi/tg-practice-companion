"""Read-only journal browsing API — Stage 2 web admin (AC-21)."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.journal_repository import JournalRepository
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/journal", tags=["journal"])


class SelfAssessmentOut(BaseModel):
    """Self-assessment block embedded in journal entry responses."""

    leads_to_goals: bool
    set_via: str


class JournalEntryOut(BaseModel):
    """Single journal entry as returned by list and detail endpoints."""

    id: uuid.UUID
    text: str
    source: str
    created_at: datetime
    practice_id: uuid.UUID | None
    practice_name: str | None
    self_assessment: SelfAssessmentOut | None


class JournalListResponse(BaseModel):
    """Paginated list of journal entries."""

    items: list[JournalEntryOut]
    total: int
    page: int
    page_size: int


def _make_repo(session: AsyncSession = Depends(get_db_session)) -> JournalRepository:  # noqa: B008
    return JournalRepository(session)


def _entry_out(row) -> JournalEntryOut:  # type: ignore[no-untyped-def]
    sa = (
        SelfAssessmentOut(leads_to_goals=row.leads_to_goals, set_via=row.assessment_set_via)
        if row.leads_to_goals is not None
        else None
    )
    return JournalEntryOut(
        id=row.id,
        text=row.text,
        source=row.source,
        created_at=row.created_at,
        practice_id=row.practice_id,
        practice_name=row.practice_name,
        self_assessment=sa,
    )


@router.get("", response_model=JournalListResponse)
async def list_journal(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    date_from: date | None = None,
    date_to: date | None = None,
    practice_id: uuid.UUID | None = None,
    repo: JournalRepository = Depends(_make_repo),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> JournalListResponse:
    """Return a paginated list of journal entries for the authenticated user.

    Supports optional filters: date_from, date_to (inclusive), practice_id.
    """
    user_id: int = current_user["id"]
    rows, total = await repo.list_paginated(
        user_id,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        practice_id=practice_id,
    )
    return JournalListResponse(
        items=[_entry_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{entry_id}", response_model=JournalEntryOut)
async def get_journal_entry(
    entry_id: uuid.UUID,
    repo: JournalRepository = Depends(_make_repo),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> JournalEntryOut:
    """Return a single journal entry by UUID."""
    row = await repo.get_by_id_with_details(entry_id, current_user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return _entry_out(row)
