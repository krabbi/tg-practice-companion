"""Integration tests for web/routers/auth.py — auth endpoints."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.repositories.user_repository import UserRepository
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
}

_OPEN_CONFIG = {
    **_BASE_CONFIG,
    "allowed_user_ids": [],
}

ALLOWED_USER_ID = 123456789
UNKNOWN_USER_ID = 999999
BOT_TOKEN = "1234567890:AAFakeTokenForTestingPurposesOnly"


def _make_init_data(
    user_id: int = ALLOWED_USER_ID,
    auth_date: int | None = None,
    bot_token: str = BOT_TOKEN,
) -> str:
    """Build a correctly signed TMA initData string."""
    if auth_date is None:
        auth_date = int(time.time())

    user = json.dumps({"id": user_id, "first_name": "Test"})
    params: dict[str, str] = {
        "user": user,
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return urlencode(params)


@pytest.fixture
async def client_with_db():
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
        yield ac, factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def open_client_with_db():
    """AsyncClient with empty allowed_user_ids (open-access mode) and DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_OPEN_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# POST /api/auth/telegram — allowlist enforced
# ---------------------------------------------------------------------------


async def test_valid_init_data_returns_token(client_with_db) -> None:
    """Valid TMA initData for an allowlisted user returns a JWT."""
    client, _ = client_with_db
    response = await client.post("/api/auth/telegram", json={"init_data": _make_init_data()})
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert isinstance(body["token"], str)


async def test_bad_init_data_returns_401(client_with_db) -> None:
    """Malformed or tampered initData returns 401."""
    client, _ = client_with_db
    bad_params = {
        "user": json.dumps({"id": ALLOWED_USER_ID}),
        "auth_date": str(int(time.time())),
        "hash": "deadbeef" * 8,
    }
    response = await client.post("/api/auth/telegram", json={"init_data": urlencode(bad_params)})
    assert response.status_code == 401


async def test_non_allowlisted_user_returns_403(client_with_db) -> None:
    """Valid initData for a user not in allowed_user_ids returns 403."""
    client, _ = client_with_db
    response = await client.post(
        "/api/auth/telegram", json={"init_data": _make_init_data(user_id=UNKNOWN_USER_ID)}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/auth/telegram — open-access (empty whitelist)
# ---------------------------------------------------------------------------


async def test_empty_whitelist_allows_unknown_user(open_client_with_db) -> None:
    """With empty allowed_user_ids, any valid initData is accepted."""
    client, _ = open_client_with_db
    response = await client.post(
        "/api/auth/telegram", json={"init_data": _make_init_data(user_id=UNKNOWN_USER_ID)}
    )
    assert response.status_code == 200
    assert "token" in response.json()


async def test_first_login_provisions_user_row(open_client_with_db) -> None:
    """POST /api/auth/telegram creates a User row in the DB on first login."""
    client, factory = open_client_with_db
    response = await client.post(
        "/api/auth/telegram", json={"init_data": _make_init_data(user_id=UNKNOWN_USER_ID)}
    )
    assert response.status_code == 200

    async with factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(UNKNOWN_USER_ID)
    assert user is not None
    assert user.telegram_id == UNKNOWN_USER_ID


async def test_second_login_is_idempotent(open_client_with_db) -> None:
    """Calling POST /api/auth/telegram twice for the same user creates exactly one row."""
    client, factory = open_client_with_db
    init_data = _make_init_data(user_id=UNKNOWN_USER_ID)

    resp1 = await client.post("/api/auth/telegram", json={"init_data": init_data})
    assert resp1.status_code == 200

    resp2 = await client.post("/api/auth/telegram", json={"init_data": init_data})
    assert resp2.status_code == 200

    async with factory() as session:
        repo = UserRepository(session)
        users = await repo.list_all()
    assert len([u for u in users if u.telegram_id == UNKNOWN_USER_ID]) == 1


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


async def test_auth_me_without_token_returns_401(client_with_db) -> None:
    """GET /api/auth/me with no Authorization header returns 401."""
    client, _ = client_with_db
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_auth_me_with_invalid_token_returns_401(client_with_db) -> None:
    """GET /api/auth/me with a garbage Bearer token returns 401."""
    client, _ = client_with_db
    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == 401


async def test_auth_me_with_valid_token_returns_claims(client_with_db) -> None:
    """GET /api/auth/me with a valid JWT returns the claims including the user id."""
    client, _ = client_with_db
    config = Config.model_validate(_BASE_CONFIG)
    token = create_jwt({"id": ALLOWED_USER_ID}, config.jwt_secret)
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == ALLOWED_USER_ID


async def test_auth_me_empty_whitelist_allows_any_valid_token(open_client_with_db) -> None:
    """GET /api/auth/me with empty whitelist accepts a JWT for any user id."""
    client, _ = open_client_with_db
    config = Config.model_validate(_OPEN_CONFIG)
    token = create_jwt({"id": UNKNOWN_USER_ID}, config.jwt_secret)
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == UNKNOWN_USER_ID
