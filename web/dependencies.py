"""FastAPI dependency providers — DB session and current-user auth."""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import verify_jwt_token

_bearer = HTTPBearer(auto_error=False)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield one AsyncSession per request from the app's session factory."""
    async with request.app.state.session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> dict:
    """Validate Bearer JWT; raise 401 on missing/invalid token, 403 if not allowlisted."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    config = request.app.state.config
    claims = verify_jwt_token(credentials.credentials, config.jwt_secret)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = claims.get("id")
    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        raise HTTPException(status_code=403, detail="Not in allowlist")

    return claims
