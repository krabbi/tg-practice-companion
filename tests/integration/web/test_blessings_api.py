"""Integration tests for web/routers/blessings.py — morning blessings CRUD + reorder API."""

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
    """GET /api/blessings with no token returns 401."""
    response = await client.get("/api/blessings")
    assert response.status_code == 401


async def test_create_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/blessings with no token returns 401."""
    response = await client.post("/api/blessings", json={"text": "May you be happy"})
    assert response.status_code == 401


async def test_reorder_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/blessings/reorder with no token returns 401."""
    response = await client.post("/api/blessings/reorder", json={"ids": []})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Round-trip: create → list → patch → delete
# ---------------------------------------------------------------------------


async def test_round_trip(client: AsyncClient, auth_headers: dict) -> None:
    """Full CRUD round-trip for a morning blessing."""
    # CREATE
    resp = await client.post(
        "/api/blessings", json={"text": "May you be happy"}, headers=auth_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "May you be happy"
    assert body["active"] is True
    assert body["rotation_order"] == 1
    blessing_id = body["id"]

    # LIST — one result
    resp = await client.get("/api/blessings", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == blessing_id

    # PATCH text
    resp = await client.patch(
        f"/api/blessings/{blessing_id}",
        json={"text": "May you be at peace"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "May you be at peace"

    # PATCH active → False
    resp = await client.patch(
        f"/api/blessings/{blessing_id}", json={"active": False}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    # DELETE
    resp = await client.delete(f"/api/blessings/{blessing_id}", headers=auth_headers)
    assert resp.status_code == 204

    # LIST after delete — empty
    resp = await client.get("/api/blessings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Rotation order auto-assignment on create
# ---------------------------------------------------------------------------


async def test_create_appends_rotation_order(client: AsyncClient, auth_headers: dict) -> None:
    """Successive creates assign rotation_order 1, 2, 3."""
    r1 = await client.post("/api/blessings", json={"text": "first"}, headers=auth_headers)
    r2 = await client.post("/api/blessings", json={"text": "second"}, headers=auth_headers)
    r3 = await client.post("/api/blessings", json={"text": "third"}, headers=auth_headers)
    assert r1.json()["rotation_order"] == 1
    assert r2.json()["rotation_order"] == 2
    assert r3.json()["rotation_order"] == 3


# ---------------------------------------------------------------------------
# Reorder: keeps unique rotation_order constraint intact
# ---------------------------------------------------------------------------


async def test_reorder_reassigns_rotation_order(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/blessings/reorder assigns rotation_order 1..N without constraint violations."""
    r1 = await client.post("/api/blessings", json={"text": "A"}, headers=auth_headers)
    r2 = await client.post("/api/blessings", json={"text": "B"}, headers=auth_headers)
    r3 = await client.post("/api/blessings", json={"text": "C"}, headers=auth_headers)
    id1, id2, id3 = r1.json()["id"], r2.json()["id"], r3.json()["id"]

    # Reverse the order: C, B, A
    resp = await client.post(
        "/api/blessings/reorder",
        json={"ids": [id3, id2, id1]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    result = {item["id"]: item["rotation_order"] for item in resp.json()}
    assert result[id3] == 1
    assert result[id2] == 2
    assert result[id1] == 3

    # List should reflect new order
    resp = await client.get("/api/blessings", headers=auth_headers)
    ordered_texts = [item["text"] for item in resp.json()]
    assert ordered_texts == ["C", "B", "A"]


async def test_reorder_missing_id_returns_400(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/blessings/reorder with a missing ID returns 400."""
    r1 = await client.post("/api/blessings", json={"text": "A"}, headers=auth_headers)
    await client.post("/api/blessings", json={"text": "B"}, headers=auth_headers)
    id1 = r1.json()["id"]
    # Only send one of the two IDs — missing the second
    resp = await client.post("/api/blessings/reorder", json={"ids": [id1]}, headers=auth_headers)
    assert resp.status_code == 400


async def test_reorder_unknown_id_returns_400(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/blessings/reorder with an unknown ID returns 400."""
    r1 = await client.post("/api/blessings", json={"text": "A"}, headers=auth_headers)
    id1 = r1.json()["id"]
    unknown = str(uuid.uuid4())
    resp = await client.post(
        "/api/blessings/reorder", json={"ids": [unknown, id1]}, headers=auth_headers
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------


async def test_patch_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """PATCH /api/blessings/{unknown} returns 404."""
    resp = await client.patch(
        f"/api/blessings/{uuid.uuid4()}", json={"text": "x"}, headers=auth_headers
    )
    assert resp.status_code == 404


async def test_delete_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/blessings/{unknown} returns 404."""
    resp = await client.delete(f"/api/blessings/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_create_empty_text_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """POST with empty text returns 422."""
    resp = await client.post("/api/blessings", json={"text": ""}, headers=auth_headers)
    assert resp.status_code == 422


async def test_patch_empty_text_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """PATCH with empty text returns 422."""
    resp = await client.post("/api/blessings", json={"text": "hello"}, headers=auth_headers)
    blessing_id = resp.json()["id"]
    resp = await client.patch(
        f"/api/blessings/{blessing_id}", json={"text": ""}, headers=auth_headers
    )
    assert resp.status_code == 422
