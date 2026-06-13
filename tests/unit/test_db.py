"""Tests for bot/db.py — engine and session factory construction."""

import os
import tempfile

import pytest

from bot.db import build_engine, build_session_factory, create_tables


def test_build_engine_returns_engine() -> None:
    """build_engine returns an async engine for a valid URL."""
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine = build_engine("sqlite+aiosqlite:///:memory:")
    assert isinstance(engine, AsyncEngine)


def test_build_session_factory_returns_factory() -> None:
    """build_session_factory returns an async_sessionmaker."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = build_session_factory("sqlite+aiosqlite:///:memory:")
    assert isinstance(factory, async_sessionmaker)


@pytest.mark.asyncio
async def test_create_tables_creates_users_table() -> None:
    """create_tables creates the users table on a SQLite file DB."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    # Use a real temp file — :memory: gives each engine its own empty DB,
    # so create_tables and the verification query must share a file.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    url = f"sqlite+aiosqlite:///{db_path}"
    try:
        await create_tables(url)

        engine = create_async_engine(url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            )
            rows = result.fetchall()
        await engine.dispose()

        assert len(rows) == 1
        assert rows[0][0] == "users"
    finally:
        os.unlink(db_path)
