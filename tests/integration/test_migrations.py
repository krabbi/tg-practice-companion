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


# ---------------------------------------------------------------------------
# 0010 — per-user content migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0010_content_tables_have_user_id(pg_engine) -> None:
    """After upgrade head, user_id column exists in all content/config tables."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    tables = (
        "practices",
        "media_assets",
        "morning_blessings",
        "motivational_images",
        "api_usage_logs",
    )

    async with pg_engine.connect() as conn:
        for table in tables:
            col_names = await conn.run_sync(
                lambda sync_conn, t=table: [c["name"] for c in inspect(sync_conn).get_columns(t)]
            )
            assert "user_id" in col_names, f"user_id missing from {table}; found: {col_names}"


@pytest.mark.asyncio
async def test_0010_user_id_not_null_on_fk_tables(pg_engine) -> None:
    """user_id must be NOT NULL on practices, media_assets, morning_blessings, motivational_images."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    fk_tables = ("practices", "media_assets", "morning_blessings", "motivational_images")

    async with pg_engine.connect() as conn:
        for table in fk_tables:
            cols = await conn.run_sync(lambda sync_conn, t=table: inspect(sync_conn).get_columns(t))
            user_id_col = next((c for c in cols if c["name"] == "user_id"), None)
            assert user_id_col is not None, f"user_id missing from {table}"
            assert not user_id_col["nullable"], (
                f"user_id must be NOT NULL in {table} but is nullable"
            )


@pytest.mark.asyncio
async def test_0010_api_usage_logs_user_id_nullable(pg_engine) -> None:
    """user_id in api_usage_logs must be nullable (attribution only)."""
    await _run_alembic_upgrade(_TEST_DB_URL)

    async with pg_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_columns("api_usage_logs")
        )
    user_id_col = next((c for c in cols if c["name"] == "user_id"), None)
    assert user_id_col is not None, "user_id missing from api_usage_logs"
    assert user_id_col["nullable"], "user_id in api_usage_logs must be nullable"


@pytest.mark.asyncio
async def test_0010_backfill_and_round_trip(pg_engine) -> None:
    """Backfill test: 0009→0010 with one user + rows fills user_id; upgrade→downgrade→upgrade."""
    import uuid as _uuid

    from alembic.config import Config as AlembicConfig

    from alembic import command

    db_url = _TEST_DB_URL

    def _upgrade_to(revision: str) -> None:
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = db_url
        try:
            cfg = AlembicConfig("alembic.ini")
            command.upgrade(cfg, revision)
        finally:
            if old is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old

    def _downgrade_to(revision: str) -> None:
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = db_url
        try:
            cfg = AlembicConfig("alembic.ini")
            command.downgrade(cfg, revision)
        finally:
            if old is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old

    # Step 1: upgrade to 0009 (one before the migration under test)
    await asyncio.to_thread(_upgrade_to, "0009")

    # Step 2: seed one user and one row in each FK table at the 0009 schema
    async with pg_engine.begin() as conn:
        tg_id = 987654321
        await conn.execute(
            text(
                "INSERT INTO users (telegram_id, language, created_at, updated_at) "
                "VALUES (:tid, 'ru', now(), now())"
            ).bindparams(tid=tg_id)
        )
        # Insert a practice row (no user_id column yet at 0009).
        # practices.id is a Postgres `uuid` column; asyncpg rejects a bare str
        # ("column id is of type uuid but expression is of type character varying"),
        # so cast the bound parameter explicitly.
        p_id = str(_uuid.uuid4())
        await conn.execute(
            text(
                "INSERT INTO practices "
                "(id, name, content_type, periodicity_type, active, sort_order, created_at, updated_at) "
                "VALUES (CAST(:id AS uuid), 'seed', 'text', 'fixed_times', true, 0, now(), now())"
            ).bindparams(id=p_id)
        )

    # Step 3: upgrade to 0010 — backfill must set user_id = tg_id
    await asyncio.to_thread(_upgrade_to, "0010")

    async with pg_engine.connect() as conn:
        row = await conn.execute(
            text("SELECT user_id FROM practices WHERE id = CAST(:id AS uuid)").bindparams(id=p_id)
        )
        user_id_val = row.scalar()

    assert user_id_val == tg_id, f"Backfill failed: expected user_id={tg_id}, got {user_id_val}"

    # Step 4: downgrade back to 0009 — user_id column should be gone
    await asyncio.to_thread(_downgrade_to, "0009")

    async with pg_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: [c["name"] for c in inspect(sync_conn).get_columns("practices")]
        )
    assert "user_id" not in cols, "user_id column should be gone after downgrade"

    # Step 5: upgrade to 0010 again (round-trip)
    await asyncio.to_thread(_upgrade_to, "0010")

    async with pg_engine.connect() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: [c["name"] for c in inspect(sync_conn).get_columns("practices")]
        )
    assert "user_id" in cols, "user_id column missing after second upgrade"
