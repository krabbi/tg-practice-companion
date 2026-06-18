"""Integration tests for web/routers/journal.py — journal read API."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.journal import JournalEntry, SelfAssessment
from bot.models.practice import Practice
from web.auth import create_jwt
from web.dependencies import get_db_session
from web.main import create_app

_BASE_CONFIG = {
    "telegram_bot_token": "1234567890:AAFakeTokenForTestingPurposesOnly",
    "anthropic_api_key": "sk-ant-fake-key-for-testing",
    "groq_api_key": "",
    "database_url": "sqlite+aiosqlite:///:memory:",
    "allowed_user_ids": "123456789",
    "jwt_secret": "super-secret-test-key",
    "cors_origins": [],
    "send_window_start": 6,
    "send_window_end": 22,
}

ALLOWED_USER_ID = 123456789
OTHER_USER_ID = 999999999


@pytest.fixture
async def engine_and_factory():
    """Shared in-memory SQLite engine with schema created once per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(engine_and_factory):
    """AsyncClient with isolated in-memory SQLite DB and get_db_session overridden."""
    engine, factory = engine_and_factory

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_BASE_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict:
    """Bearer JWT headers for the allowlisted test user."""
    config = Config.model_validate(_BASE_CONFIG)
    token = create_jwt({"id": ALLOWED_USER_ID}, config.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded(engine_and_factory):
    """Seed journal entries, a practice, and self-assessments; return inserted ids."""
    _, factory = engine_and_factory
    async with factory() as session:
        practice = Practice(
            name="Morning Question",
            content_type="question",
            content="How do you feel?",
            periodicity_type="fixed_times",
            schedule_times=["09:00"],
            user_id=ALLOWED_USER_ID,
        )
        session.add(practice)
        await session.flush()

        entry1 = JournalEntry(
            user_id=ALLOWED_USER_ID,
            practice_id=practice.id,
            text="I feel great",
            source="text",
            created_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        )
        entry2 = JournalEntry(
            user_id=ALLOWED_USER_ID,
            practice_id=None,
            text="Voice note transcript",
            source="voice",
            created_at=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        )
        entry3 = JournalEntry(
            user_id=ALLOWED_USER_ID,
            practice_id=practice.id,
            text="Another entry",
            source="text",
            created_at=datetime(2026, 6, 3, 9, 0, tzinfo=UTC),
        )
        session.add_all([entry1, entry2, entry3])
        await session.flush()

        sa1 = SelfAssessment(
            journal_entry_id=entry1.id,
            leads_to_goals=True,
            set_via="button",
        )
        session.add(sa1)
        await session.flush()
        await session.commit()

    return {
        "practice_id": practice.id,
        "entry1_id": entry1.id,
        "entry2_id": entry2.id,
        "entry3_id": entry3.id,
    }


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


async def test_list_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/journal with no token returns 401."""
    resp = await client.get("/api/journal")
    assert resp.status_code == 401


async def test_get_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/journal/{id} with no token returns 401."""
    resp = await client.get(f"/api/journal/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Basic list
# ---------------------------------------------------------------------------


async def test_list_empty(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/journal returns empty list when no entries exist."""
    resp = await client.get("/api/journal", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_list_returns_seeded_entries(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """GET /api/journal returns all seeded entries with correct fields."""
    resp = await client.get("/api/journal", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_list_entry_with_assessment(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """Entry with self-assessment includes leads_to_goals and set_via."""
    resp = await client.get("/api/journal", headers=auth_headers)
    items = {i["id"]: i for i in resp.json()["items"]}

    e1 = items[str(seeded["entry1_id"])]
    assert e1["self_assessment"] is not None
    assert e1["self_assessment"]["leads_to_goals"] is True
    assert e1["self_assessment"]["set_via"] == "button"
    assert e1["practice_name"] == "Morning Question"


async def test_list_entry_without_assessment(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """Entry without self-assessment has self_assessment=null."""
    resp = await client.get("/api/journal", headers=auth_headers)
    items = {i["id"]: i for i in resp.json()["items"]}
    e2 = items[str(seeded["entry2_id"])]
    assert e2["self_assessment"] is None
    assert e2["practice_name"] is None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


async def test_pagination_page_size(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """page_size=1 returns only 1 item but total stays correct."""
    resp = await client.get("/api/journal?page=1&page_size=1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["page"] == 1
    assert body["page_size"] == 1


async def test_pagination_second_page(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """page=2&page_size=2 returns the remaining 1 item."""
    resp = await client.get("/api/journal?page=2&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


async def test_list_sorted_by_created_at_desc(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """Entries are returned newest first."""
    resp = await client.get("/api/journal", headers=auth_headers)
    items = resp.json()["items"]
    dates = [i["created_at"] for i in items]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Date filter
# ---------------------------------------------------------------------------


async def test_date_from_filter(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """date_from filters out older entries."""
    resp = await client.get("/api/journal?date_from=2026-06-02", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = {i["id"] for i in body["items"]}
    assert str(seeded["entry1_id"]) not in ids


async def test_date_to_filter(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """date_to filters out newer entries."""
    resp = await client.get("/api/journal?date_to=2026-06-01", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(seeded["entry1_id"])


async def test_date_range_filter(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """date_from + date_to returns only entries in [from, to] inclusive."""
    resp = await client.get(
        "/api/journal?date_from=2026-06-01&date_to=2026-06-02", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Practice filter
# ---------------------------------------------------------------------------


async def test_practice_id_filter(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """practice_id filter returns only entries linked to that practice."""
    pid = seeded["practice_id"]
    resp = await client.get(f"/api/journal?practice_id={pid}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["practice_id"] == str(pid)


async def test_unknown_practice_id_returns_empty(
    client: AsyncClient, auth_headers: dict, seeded: dict
) -> None:
    """practice_id for non-existent practice returns empty list."""
    resp = await client.get(f"/api/journal?practice_id={uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Single entry GET
# ---------------------------------------------------------------------------


async def test_get_single_entry(client: AsyncClient, auth_headers: dict, seeded: dict) -> None:
    """GET /api/journal/{id} returns correct entry with details."""
    eid = seeded["entry1_id"]
    resp = await client.get(f"/api/journal/{eid}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(eid)
    assert body["text"] == "I feel great"
    assert body["source"] == "text"
    assert body["practice_name"] == "Morning Question"
    assert body["self_assessment"]["leads_to_goals"] is True


async def test_get_nonexistent_entry_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/journal/{unknown} returns 404."""
    resp = await client.get(f"/api/journal/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
