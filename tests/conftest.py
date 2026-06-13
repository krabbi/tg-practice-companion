"""Root conftest — shared fixtures for unit and integration tests.

`fake_config` constructs the real bot.config.Config with safe test values so that
every unit test uses the same field validation logic as production.

`db_session` provides an aiosqlite :memory: session with all ORM tables created
and dropped per test. Repository/integration tests use this fixture.
SQLite shims: Enum renders as VARCHAR+CHECK, JSON as JSON1 text, Numeric returns
float/str (compare with tolerance or cast). Migration tests (test_migrations.py)
run against real Postgres 16 via a GitHub Actions service container.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def fake_config() -> Config:
    """Return a credentials-free Config instance for unit tests."""
    return Config.model_validate(
        {
            "telegram_bot_token": "1234567890:AAFakeTokenForTestingPurposesOnly",
            "anthropic_api_key": "sk-ant-fake-key-for-testing",
            "groq_api_key": "",
            "database_url": _TEST_DB_URL,
            "allowed_user_ids": "123456789",
            "monthly_cost_limit_usd": 10.0,
            "analysis_cost_cap_usd": 0.05,
            "default_language": "ru",
            "send_window_start": 6,
            "send_window_end": 22,
        }
    )


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    """Yield an async SQLite :memory: session with all tables created.

    Tables are created before the test and the engine is disposed after,
    giving each test a clean isolated DB.
    """
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
