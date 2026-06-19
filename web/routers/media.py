"""REST API for media assets and motivational-image pool — Stage 2 web admin (B4)."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.image_repository import ImageRepository
from bot.repositories.media_asset_repository import MediaAssetRepository
from bot.services.media_service import MediaAdminService, MediaAssetError
from web.dependencies import get_current_user, get_db_session

media_router = APIRouter(prefix="/api/media", tags=["media"])
motivational_router = APIRouter(prefix="/api/motivational-images", tags=["motivational-images"])


class MediaAssetResponse(BaseModel):
    """MediaAsset representation returned by all media endpoints."""

    id: uuid.UUID
    kind: str
    storage_path: str | None
    telegram_file_id: str | None
    mime: str | None
    original_filename: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresignedUrlResponse(BaseModel):
    """Response for GET /api/media/{asset_id}/url."""

    url: str
    expires_in: int


class MotivationalImageCreate(BaseModel):
    """Request body for POST /api/motivational-images."""

    media_asset_id: uuid.UUID
    active: bool = True


class MotivationalImageResponse(BaseModel):
    """MotivationalImage representation returned by POST /api/motivational-images."""

    id: uuid.UUID
    media_asset_id: uuid.UUID
    active: bool

    model_config = {"from_attributes": True}


def _make_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> MediaAdminService:
    """Build MediaAdminService from request context."""
    bot = getattr(request.app.state, "bot", None)
    storage = request.app.state.storage_service
    return MediaAdminService(
        session,
        MediaAssetRepository(session),
        ImageRepository(session),
        bot,
        current_user["id"],
        storage,
    )


@media_router.post("", response_model=MediaAssetResponse, status_code=201)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    kind: Literal["audio", "image", "video"] = Form(...),  # noqa: B008
    service: MediaAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Upload an audio, image, or video file; persist to S3 and capture a Telegram file_id."""
    config = request.app.state.config
    max_bytes: int = (
        config.media_max_image_bytes if kind == "image" else config.media_max_audio_bytes
    )
    limit_mb = max_bytes // (1024 * 1024)
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {limit_mb} MB)")
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {limit_mb} MB)")
    filename = file.filename or f"upload.{kind}"
    _default_mime = {"audio": "audio/mpeg", "image": "image/jpeg", "video": "video/mp4"}
    mime = file.content_type or _default_mime.get(kind, "application/octet-stream")
    try:
        return await service.upload(data, filename, kind, mime, current_user["id"])
    except MediaAssetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@media_router.get("", response_model=list[MediaAssetResponse])
async def list_media(
    kind: Literal["audio", "image", "video"] | None = None,
    service: MediaAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> list:
    """List all media assets, optionally filtered by ?kind=audio|image."""
    return await service.list_assets(current_user["id"], kind)


@media_router.get("/{asset_id}/url", response_model=PresignedUrlResponse)
async def get_media_url(
    asset_id: uuid.UUID,
    request: Request,
    service: MediaAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> PresignedUrlResponse:
    """Return a short-lived presigned GET URL for the asset's S3 object."""
    asset = await service.get_asset(asset_id, current_user["id"])
    if asset is None or asset.storage_path is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    config = request.app.state.config
    url = service.generate_presigned_url(asset.storage_path, config.s3_presign_expiry_seconds)
    return PresignedUrlResponse(url=url, expires_in=config.s3_presign_expiry_seconds)


@media_router.delete("/{asset_id}", status_code=204)
async def delete_media(
    asset_id: uuid.UUID,
    service: MediaAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete a media asset row and its S3 object (best-effort)."""
    found = await service.delete_asset(asset_id, current_user["id"])
    if not found:
        raise HTTPException(status_code=404, detail="Media asset not found")


@motivational_router.post("", response_model=MotivationalImageResponse, status_code=201)
async def create_motivational_image(
    body: MotivationalImageCreate,
    service: MediaAdminService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> object:
    """Add a MediaAsset to the motivational-image pool."""
    try:
        return await service.create_motivational_image(
            body.media_asset_id, current_user["id"], body.active
        )
    except MediaAssetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
