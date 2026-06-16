"""REST CRUD for Practice rows — Stage 2 web admin API."""

import re
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.practice_repository import PracticeRepository
from bot.services.practice_admin_service import PracticeAdminService, PracticeValidationError
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/practices", tags=["practices"])

_ContentType = Literal[
    "question", "text", "audio", "image", "want", "good_deeds", "motivational_image"
]
_PeriodicityType = Literal["every_n_hours", "fixed_times"]
_HHMM_RE = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")


class PracticeCreate(BaseModel):
    """Request body for POST /api/practices."""

    name: str
    content_type: _ContentType
    content: str | None = None
    media_asset_id: uuid.UUID | None = None
    periodicity_type: _PeriodicityType
    interval_hours: int | None = None
    schedule_times: list[str] | None = None
    anchor_hour: int = 0
    anchor_minute: int = 0
    active: bool = True
    start_date: datetime | None = None
    end_date: datetime | None = None
    sort_order: int = 0

    @field_validator("schedule_times")
    @classmethod
    def _validate_hhmm(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [t for t in v if not _HHMM_RE.match(t)]
        if bad:
            raise ValueError(f"Invalid HH:MM entries in schedule_times: {bad!r}")
        return v

    @model_validator(mode="after")
    def _require_interval_hours(self) -> "PracticeCreate":
        if self.periodicity_type == "every_n_hours" and self.interval_hours is None:
            raise ValueError("interval_hours is required when periodicity_type is every_n_hours")
        return self


class PracticeUpdate(BaseModel):
    """Request body for PATCH /api/practices/{id} — all fields optional."""

    name: str | None = None
    content_type: _ContentType | None = None
    content: str | None = None
    media_asset_id: uuid.UUID | None = None
    periodicity_type: _PeriodicityType | None = None
    interval_hours: int | None = None
    schedule_times: list[str] | None = None
    anchor_hour: int | None = None
    anchor_minute: int | None = None
    active: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    sort_order: int | None = None

    @field_validator("schedule_times")
    @classmethod
    def _validate_hhmm(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [t for t in v if not _HHMM_RE.match(t)]
        if bad:
            raise ValueError(f"Invalid HH:MM entries in schedule_times: {bad!r}")
        return v


class PracticeResponse(BaseModel):
    """Practice representation returned by all endpoints."""

    id: uuid.UUID
    name: str
    content_type: str
    content: str | None
    media_asset_id: uuid.UUID | None
    periodicity_type: str
    interval_hours: int | None
    schedule_times: list[str] | None
    anchor_hour: int | None
    anchor_minute: int | None
    active: bool
    start_date: datetime | None
    end_date: datetime | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _make_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> PracticeAdminService:
    """Build PracticeAdminService from request context."""
    config = request.app.state.config
    return PracticeAdminService(
        session,
        PracticeRepository(session),
        config.send_window_start,
        config.send_window_end,
    )


@router.get("", response_model=list[PracticeResponse])
async def list_practices(
    active: bool | None = None,
    service: PracticeAdminService = Depends(_make_service),  # noqa: B008
    _: dict = Depends(get_current_user),  # noqa: B008
) -> list:
    """List all practices, optionally filtered by ?active=true|false."""
    return await service.list_all(active)


@router.get("/{practice_id}", response_model=PracticeResponse)
async def get_practice(
    practice_id: uuid.UUID,
    service: PracticeAdminService = Depends(_make_service),  # noqa: B008
    _: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Return a single practice by UUID."""
    practice = await service.get(practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


@router.post("", response_model=PracticeResponse, status_code=201)
async def create_practice(
    body: PracticeCreate,
    service: PracticeAdminService = Depends(_make_service),  # noqa: B008
    _: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Create a new practice."""
    try:
        return await service.create(**body.model_dump())
    except PracticeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{practice_id}", response_model=PracticeResponse)
async def update_practice(
    practice_id: uuid.UUID,
    body: PracticeUpdate,
    service: PracticeAdminService = Depends(_make_service),  # noqa: B008
    _: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Partially update a practice (only supplied fields are changed)."""
    updates = body.model_dump(exclude_unset=True)
    try:
        practice = await service.update(practice_id, updates)
    except PracticeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


@router.delete("/{practice_id}", status_code=204)
async def delete_practice(
    practice_id: uuid.UUID,
    service: PracticeAdminService = Depends(_make_service),  # noqa: B008
    _: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a practice by UUID."""
    found = await service.delete(practice_id)
    if not found:
        raise HTTPException(status_code=404, detail="Practice not found")
