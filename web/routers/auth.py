"""Authentication router — TMA initData → JWT."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from web.auth import create_jwt, verify_telegram_init_data
from web.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    """Request body for POST /api/auth/telegram."""

    init_data: str


@router.post("/telegram")
async def auth_telegram(body: TelegramAuthRequest, request: Request) -> dict:
    """Validate TMA initData and issue a JWT for an allowlisted user."""
    config = request.app.state.config
    user = verify_telegram_init_data(body.init_data, config.telegram_bot_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user_id = user.get("id")
    if user_id not in config.allowed_user_ids:
        raise HTTPException(status_code=403, detail="Not in allowlist")

    token = create_jwt({"id": user_id}, config.jwt_secret)
    return {"token": token}


@router.get("/me")
async def auth_me(claims: dict = Depends(get_current_user)) -> dict:  # noqa: B008
    """Return the current user's JWT claims."""
    return claims
