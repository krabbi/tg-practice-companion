"""Integration tests for web/routers/wants.py — want-list CRUD API."""

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


@pytest.fixture
async def client() -> AsyncClient:
    """AsyncClient with isolated in-memory SQLite and get_db_session overridden."""
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
# Auth guards
# ---------------------------------------------------------------------------


async def test_list_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/wants with no token returns 401."""
    response = await client.get("/api/wants")
    assert response.status_code == 401


async def test_create_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/wants with no token returns 401."""
    response = await client.post("/api/wants", json={"text": "buy a guitar"})
    assert response.status_code == 401


async def test_patch_without_token_returns_401(client: AsyncClient) -> None:
    """PATCH /api/wants/{id} with no token returns 401."""
    response = await client.patch(f"/api/wants/{uuid.uuid4()}", json={"done": True})
    assert response.status_code == 401


async def test_delete_without_token_returns_401(client: AsyncClient) -> None:
    """DELETE /api/wants/{id} with no token returns 401."""
    response = await client.delete(f"/api/wants/{uuid.uuid4()}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Round-trip: create → list → patch text → toggle done → delete
# ---------------------------------------------------------------------------


async def test_round_trip(client: AsyncClient, auth_headers: dict) -> None:
    """Full CRUD round-trip for a want-list item."""
    # CREATE
    resp = await client.post("/api/wants", json={"text": "buy a guitar"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "buy a guitar"
    assert body["done"] is False
    assert body["user_id"] == ALLOWED_USER_ID
    want_id = body["id"]

    # LIST — one result
    resp = await client.get("/api/wants", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == want_id

    # PATCH text
    resp = await client.patch(
        f"/api/wants/{want_id}", json={"text": "buy a piano"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "buy a piano"

    # PATCH done
    resp = await client.patch(f"/api/wants/{want_id}", json={"done": True}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["done"] is True

    # DELETE
    resp = await client.delete(f"/api/wants/{want_id}", headers=auth_headers)
    assert resp.status_code == 204

    # LIST after delete — empty
    resp = await client.get("/api/wants", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------


async def test_patch_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """PATCH /api/wants/{unknown} returns 404."""
    resp = await client.patch(
        f"/api/wants/{uuid.uuid4()}", json={"text": "x"}, headers=auth_headers
    )
    assert resp.status_code == 404


async def test_delete_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/wants/{unknown} returns 404."""
    resp = await client.delete(f"/api/wants/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_create_empty_text_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """POST with empty text returns 422."""
    resp = await client.post("/api/wants", json={"text": ""}, headers=auth_headers)
    assert resp.status_code == 422


async def test_patch_empty_text_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """PATCH with empty text returns 422."""
    resp = await client.post("/api/wants", json={"text": "buy a guitar"}, headers=auth_headers)
    want_id = resp.json()["id"]
    resp = await client.patch(f"/api/wants/{want_id}", json={"text": ""}, headers=auth_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Multiple items: list ordering (oldest first)
# ---------------------------------------------------------------------------


async def test_list_ordering_oldest_first(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/wants returns items oldest first."""
    r1 = await client.post("/api/wants", json={"text": "first"}, headers=auth_headers)
    r2 = await client.post("/api/wants", json={"text": "second"}, headers=auth_headers)
    resp = await client.get("/api/wants", headers=auth_headers)
    items = resp.json()
    assert len(items) == 2
    assert items[0]["id"] == r1.json()["id"]
    assert items[1]["id"] == r2.json()["id"]
