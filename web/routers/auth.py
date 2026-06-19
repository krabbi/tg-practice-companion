"""Authentication router — TMA initData → JWT."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.user_repository import UserRepository
from bot.services.user_service import UserService
from web.auth import create_jwt, verify_telegram_init_data
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    """Request body for POST /api/auth/telegram."""

    init_data: str


@router.post("/telegram")
async def auth_telegram(
    body: TelegramAuthRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Validate TMA initData, optionally enforce allowlist, provision user, and issue JWT."""
    config = request.app.state.config
    user = verify_telegram_init_data(body.init_data, config.telegram_bot_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user_id = user.get("id")
    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        raise HTTPException(status_code=403, detail="Not in allowlist")

    user_service = UserService(session, UserRepository(session))
    await user_service.get_or_create(user_id, language=config.default_language)

    token = create_jwt({"id": user_id}, config.jwt_secret)
    return {"token": token}


@router.get("/me")
async def auth_me(claims: dict = Depends(get_current_user)) -> dict:  # noqa: B008
    """Return the current user's JWT claims."""
    return claims
