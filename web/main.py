"""FastAPI application factory for the Stage 2 web companion."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bot.config import Config
from bot.db import build_session_factory
from web.routers.auth import router as auth_router
from web.routers.practices import router as practices_router


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.session_factory = session_factory
        yield

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

    return app
