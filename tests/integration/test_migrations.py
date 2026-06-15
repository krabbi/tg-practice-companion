"""Integration test: alembic upgrade head against real Postgres 16.

Skipped automatically when TEST_DATABASE_URL is not set (local dev without
Postgres). In CI a Postgres 16 service container is started and
TEST_DATABASE_URL is injected by the workflow.

Why Postgres and not SQLite: engine-specific column types (Enum, JSON,
Numeric(10,6), DateTime(timezone=True)) appear from M1 onwards. Testing
migrations against the real engine ensures that column types, server defaults,
and constraints are rendered correctly for Postgres.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason="TEST_DATABASE_URL not set — skipping Postgres migration test",
)


@pytest_asyncio.fixture
async def pg_engine():
    """Create a fresh async engine; drop migrated tables after each test."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    yield engine
    # Clean up so repeated local runs and multi-test CI runs stay hermetic.
    # Tables must be dropped in FK-dependency order (children before parents).
    # Enum types are Postgres-only constructs that survive DROP TABLE and must
    # be dropped explicitly; IF EXISTS keeps this a no-op on SQLite.
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        # M4 list tables (no FKs, drop first for safety).
        await conn.execute(text("DROP TABLE IF EXISTS want_list_items"))
        await conn.execute(text("DROP TABLE IF EXISTS good_deeds"))
        # M3 morning tables first: motivational_images FKs media_assets and
        # daily_ai_analyses references users, so they must precede those parents.
        await conn.execute(text("DROP TABLE IF EXISTS api_usage_logs"))
        await conn.execute(text("DROP TABLE IF EXISTS daily_ai_analyses"))
        await conn.execute(text("DROP TABLE IF EXISTS motivational_images"))
        await conn.execute(text("DROP TABLE IF EXISTS morning_blessings"))
        # M2 journal tables (children of practices / journal_entries) first.
        await conn.execute(text("DROP TABLE IF EXISTS self_assessments"))
        await conn.execute(text("DROP TABLE IF EXISTS journal_entries"))
        await conn.execute(text("DROP TABLE IF EXISTS pending_prompts"))
        await conn.execute(text("DROP TABLE IF EXISTS practice_sends"))
        await conn.execute(text("DROP TABLE IF EXISTS practices"))
        await conn.execute(text("DROP TABLE IF EXISTS media_assets"))
        await conn.execute(text("DROP TABLE IF EXISTS users"))
        await conn.execute(text("DROP TYPE IF EXISTS api_usage_kind"))
        await conn.execute(text("DROP TYPE IF EXISTS assessment_set_via"))
        await conn.execute(text("DROP TYPE IF EXISTS entry_source"))
        await conn.execute(text("DROP TYPE IF EXISTS prompt_kind"))
        await conn.execute(text("DROP TYPE IF EXISTS practice_periodicity_type"))
        await conn.execute(text("DROP TYPE IF EXISTS practice_content_type"))
        await conn.execute(text("DROP TYPE IF EXISTS media_asset_kind"))
    await engine.dispose()


def _run_alembic_upgrade_sync(db_url: str) -> None:
    """Run ``alembic upgrade head`` synchronously (called from async via executor)."""
    # Temporarily set DATABASE_URL so that alembic/env.py picks it up.
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        cfg = AlembicConfig("alembic.ini")
        command.upgrade(cfg, "head")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


async def _run_alembic_upgrade(db_url: str) -> None:
    """Run ``alembic upgrade head`` programmatically against *db_url*.

    Delegates to a thread so that alembic/env.py's ``asyncio.run()`` call does
    not collide with the already-running pytest-asyncio event loop.
    """
    await asyncio.to_thread(_run_alembic_upgrade_sync, db_url)


@pytest.mark.asyncio
async def test_upgrade_head_creates_users_table(pg_engine) -> None:
    """alembic upgrade head from empty DB must create the users table."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    async with pg_engine.connect() as conn:
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    assert "users" in table_names, f"users table missing; found: {table_names}"


@pytest.mark.asyncio
async def test_upgrade_head_users_has_tz_changed_at(pg_engine) -> None:
    """After upgrade head the users table must include the tz_changed_at column."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    async with pg_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: [col["name"] for col in inspect(sync_conn).get_columns("users")]
        )

    assert "tz_changed_at" in columns, (
        f"tz_changed_at column missing from users; found columns: {columns}"
    )


@pytest.mark.asyncio
async def test_upgrade_head_users_columns_complete(pg_engine) -> None:
    """After upgrade head users must have all seven columns defined in the schema."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    expected = {
        "telegram_id",
        "timezone",
        "language",
        "skip_until",
        "tz_changed_at",
        "created_at",
        "updated_at",
    }

    async with pg_engine.connect() as conn:
        actual = await conn.run_sync(
            lambda sync_conn: {col["name"] for col in inspect(sync_conn).get_columns("users")}
        )

    missing = expected - actual
    assert not missing, f"Missing columns in users table: {missing}"
