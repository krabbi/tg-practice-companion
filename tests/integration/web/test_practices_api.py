"""Integration tests for web/routers/practices.py — practices CRUD API."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
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

_VALID_FIXED = {
    "name": "Morning Question",
    "content_type": "question",
    "content": "How do you feel today?",
    "periodicity_type": "fixed_times",
    "schedule_times": ["09:00", "15:00"],
}

_VALID_HOURLY = {
    "name": "Hourly Check",
    "content_type": "text",
    "content": "Check in",
    "periodicity_type": "every_n_hours",
    "interval_hours": 2,
    "anchor_hour": 6,
}


@pytest.fixture
async def client() -> AsyncClient:
    """AsyncClient with an isolated in-memory SQLite DB and get_db_session overridden."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_BASE_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def auth_headers() -> dict:
    """Bearer JWT headers for the allowlisted test user."""
    config = Config.model_validate(_BASE_CONFIG)
    token = create_jwt({"id": ALLOWED_USER_ID}, config.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


async def test_list_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/practices with no token returns 401."""
    response = await client.get("/api/practices")
    assert response.status_code == 401


async def test_create_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/practices with no token returns 401."""
    response = await client.post("/api/practices", json=_VALID_FIXED)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Round-trip: create → list → get → patch → delete
# ---------------------------------------------------------------------------


async def test_round_trip(client: AsyncClient, auth_headers: dict) -> None:
    """Full CRUD round-trip for a fixed_times practice."""
    # CREATE
    resp = await client.post("/api/practices", json=_VALID_FIXED, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Morning Question"
    assert body["content_type"] == "question"
    assert body["schedule_times"] == ["09:00", "15:00"]
    practice_id = body["id"]

    # LIST — one result
    resp = await client.get("/api/practices", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == practice_id

    # GET by ID
    resp = await client.get(f"/api/practices/{practice_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Morning Question"

    # PATCH — rename
    resp = await client.patch(
        f"/api/practices/{practice_id}",
        json={"name": "Renamed Question"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Question"

    # DELETE
    resp = await client.delete(f"/api/practices/{practice_id}", headers=auth_headers)
    assert resp.status_code == 204

    # GET after delete → 404
    resp = await client.get(f"/api/practices/{practice_id}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# every_n_hours practice
# ---------------------------------------------------------------------------


async def test_create_every_n_hours_practice(client: AsyncClient, auth_headers: dict) -> None:
    """Create an every_n_hours practice with a valid anchor_hour."""
    resp = await client.post("/api/practices", json=_VALID_HOURLY, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["periodicity_type"] == "every_n_hours"
    assert body["interval_hours"] == 2


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_invalid_fixed_times_format_returns_422(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST with malformed schedule_times entries returns 422."""
    data = {**_VALID_FIXED, "schedule_times": ["9:00", "25:61"]}
    resp = await client.post("/api/practices", json=data, headers=auth_headers)
    assert resp.status_code == 422


async def test_every_n_hours_without_interval_returns_422(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST every_n_hours without interval_hours returns 422."""
    data = {
        "name": "Bad Practice",
        "content_type": "text",
        "content": "Check in",
        "periodicity_type": "every_n_hours",
        # interval_hours missing
    }
    resp = await client.post("/api/practices", json=data, headers=auth_headers)
    assert resp.status_code == 422


async def test_anchor_outside_window_returns_400(client: AsyncClient, auth_headers: dict) -> None:
    """POST with anchor_hour that yields no slot inside the send window returns 400."""
    data = {
        "name": "Night Practice",
        "content_type": "text",
        "content": "Night check",
        "periodicity_type": "every_n_hours",
        "interval_hours": 24,
        "anchor_hour": 3,  # 03:00 — outside [06:00, 22:00)
    }
    resp = await client.post("/api/practices", json=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "never fire" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Filter by active
# ---------------------------------------------------------------------------


async def test_list_filter_active(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/practices?active= filters by active flag."""
    await client.post("/api/practices", json=_VALID_FIXED, headers=auth_headers)
    inactive = {**_VALID_FIXED, "name": "Inactive Practice", "active": False}
    await client.post("/api/practices", json=inactive, headers=auth_headers)

    resp = await client.get("/api/practices?active=true", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["active"] is True

    resp = await client.get("/api/practices?active=false", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["active"] is False


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------


async def test_get_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/practices/{unknown} returns 404."""
    resp = await client.get(f"/api/practices/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


async def test_patch_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """PATCH /api/practices/{unknown} returns 404."""
    resp = await client.patch(
        f"/api/practices/{uuid.uuid4()}",
        json={"name": "Does not exist"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_delete_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/practices/{unknown} returns 404."""
    resp = await client.delete(f"/api/practices/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
