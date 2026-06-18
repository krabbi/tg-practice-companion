"""FastAPI application factory for the Stage 2 web companion."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bot.config import Config
from bot.db import build_session_factory
from bot.services.storage_service import S3StorageService
from web.routers.auth import router as auth_router
from web.routers.blessings import router as blessings_router
from web.routers.journal import router as journal_router
from web.routers.media import media_router, motivational_router
from web.routers.practices import router as practices_router
from web.routers.reports import router as reports_router
from web.routers.wants import router as wants_router


def create_app(config: Config | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    Raises ValueError if JWT_SECRET is unset, so misconfigured deployments
    fail at startup rather than at the first authenticated request.
    """
    if config is None:
        config = Config()  # type: ignore[call-arg]

    if not config.jwt_secret:
        raise ValueError("JWT_SECRET must be set before starting the web service")

    session_factory = build_session_factory(config.database_url)

    # Build S3 storage service only when all required vars are present; absent in Stage 1.
    storage_service: S3StorageService | None = None
    if config.s3_bucket and config.s3_access_key_id and config.s3_secret_access_key:
        storage_service = S3StorageService.from_config(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        from aiogram import Bot

        app.state.session_factory = session_factory
        app.state.storage_service = storage_service
        # Create a Bot for Telegram file uploads unless one was injected externally (e.g. tests).
        own_bot = not getattr(app.state, "bot", None)
        if own_bot:
            app.state.bot = Bot(token=config.telegram_bot_token)
        try:
            yield
        finally:
            if own_bot and getattr(app.state, "bot", None):
                await app.state.bot.session.close()

    app = FastAPI(title="tg-practice-companion web", lifespan=lifespan)
    app.state.config = config

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Return service liveness."""
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(practices_router)
    app.include_router(journal_router)
    app.include_router(reports_router)
    app.include_router(media_router)
    app.include_router(motivational_router)
    app.include_router(wants_router)
    app.include_router(blessings_router)

    return app
