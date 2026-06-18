"""REST CRUD for WantListItem rows — Stage 2 web admin API."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.want_list_repository import WantListRepository
from bot.services.want_admin_service import WantAdminService
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/wants", tags=["wants"])


class WantCreate(BaseModel):
    """Request body for POST /api/wants."""

    text: str = Field(..., min_length=1)


class WantUpdate(BaseModel):
    """Request body for PATCH /api/wants/{id} — all fields optional."""

    text: str | None = Field(None, min_length=1)
    done: bool | None = None


class WantResponse(BaseModel):
    """WantListItem representation returned by all endpoints."""

    id: uuid.UUID
    user_id: int
    text: str
    done: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def _make_service(session: AsyncSession = Depends(get_db_session)) -> WantAdminService:  # noqa: B008
    """Build WantAdminService from request session."""
    return WantAdminService(session, WantListRepository(session))


@router.get("", response_model=list[WantResponse])
async def list_wants(
    service: WantAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> list:
    """List all want-list items for the authenticated user."""
    return await service.list_for_user(current_user["id"])


@router.post("", response_model=WantResponse, status_code=201)
async def create_want(
    body: WantCreate,
    service: WantAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Create a new want-list item for the authenticated user."""
    return await service.create(user_id=current_user["id"], text=body.text)


@router.patch("/{want_id}", response_model=WantResponse)
async def update_want(
    want_id: uuid.UUID,
    body: WantUpdate,
    service: WantAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Partially update a want-list item (text and/or done)."""
    updates = body.model_dump(exclude_unset=True)
    item = await service.update(want_id, current_user["id"], **updates)
    if item is None:
        raise HTTPException(status_code=404, detail="Want not found")
    return item


@router.delete("/{want_id}", status_code=204)
async def delete_want(
    want_id: uuid.UUID,
    service: WantAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a want-list item by UUID."""
    found = await service.delete(want_id, current_user["id"])
    if not found:
        raise HTTPException(status_code=404, detail="Want not found")
