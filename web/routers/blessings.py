"""REST CRUD + reorder for MorningBlessing rows — Stage 2 web admin API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.blessing_repository import BlessingRepository
from bot.services.blessing_admin_service import BlessingAdminService
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/blessings", tags=["blessings"])


class BlessingCreate(BaseModel):
    """Request body for POST /api/blessings."""

    text: str = Field(..., min_length=1)
    active: bool = True


class BlessingUpdate(BaseModel):
    """Request body for PATCH /api/blessings/{id} — all fields optional."""

    text: str | None = Field(None, min_length=1)
    active: bool | None = None


class BlessingReorder(BaseModel):
    """Request body for POST /api/blessings/reorder."""

    ids: list[uuid.UUID] = Field(..., min_length=1)


class BlessingResponse(BaseModel):
    """MorningBlessing representation returned by all endpoints."""

    id: uuid.UUID
    text: str
    rotation_order: int
    active: bool

    model_config = {"from_attributes": True}


def _make_service(session: AsyncSession = Depends(get_db_session)) -> BlessingAdminService:  # noqa: B008
    """Build BlessingAdminService from request session."""
    return BlessingAdminService(session, BlessingRepository(session))


@router.get("", response_model=list[BlessingResponse])
async def list_blessings(
    service: BlessingAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> list:
    """List all morning blessings ordered by rotation_order."""
    return await service.list_all(current_user["id"])


@router.post("", response_model=BlessingResponse, status_code=201)
async def create_blessing(
    body: BlessingCreate,
    service: BlessingAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Create a new morning blessing appended to the end of the rotation order."""
    return await service.create(user_id=current_user["id"], text=body.text, active=body.active)


@router.post("/reorder", response_model=list[BlessingResponse])
async def reorder_blessings(
    body: BlessingReorder,
    service: BlessingAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> list:
    """Reassign rotation_order 1..N to all blessings in the supplied order.

    The request must include every existing blessing ID exactly once.
    """
    try:
        return await service.reorder(body.ids, current_user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{blessing_id}", response_model=BlessingResponse)
async def update_blessing(
    blessing_id: uuid.UUID,
    body: BlessingUpdate,
    service: BlessingAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Partially update a morning blessing (text and/or active)."""
    updates = body.model_dump(exclude_unset=True)
    blessing = await service.update(blessing_id, current_user["id"], **updates)
    if blessing is None:
        raise HTTPException(status_code=404, detail="Blessing not found")
    return blessing


@router.delete("/{blessing_id}", status_code=204)
async def delete_blessing(
    blessing_id: uuid.UUID,
    service: BlessingAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a morning blessing by UUID."""
    found = await service.delete(blessing_id, current_user["id"])
    if not found:
        raise HTTPException(status_code=404, detail="Blessing not found")
