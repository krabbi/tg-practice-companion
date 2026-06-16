"""Integration tests for web/routers/auth.py — auth endpoints."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from bot.config import Config
from web.auth import create_jwt
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

ALLOWED_USER_ID = 123456789
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
def test_config() -> Config:
    """Config with a valid jwt_secret for web tests."""
    return Config.model_validate(_BASE_CONFIG)


@pytest.fixture
def client(test_config: Config) -> TestClient:
    """TestClient for the full FastAPI app."""
    return TestClient(create_app(test_config))


# ---------------------------------------------------------------------------
# POST /api/auth/telegram
# ---------------------------------------------------------------------------


def test_valid_init_data_returns_token(client: TestClient) -> None:
    """Valid TMA initData for an allowlisted user returns a JWT."""
    response = client.post("/api/auth/telegram", json={"init_data": _make_init_data()})
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert isinstance(body["token"], str)


def test_bad_init_data_returns_401(client: TestClient) -> None:
    """Malformed or tampered initData returns 401."""
    bad_params = {
        "user": json.dumps({"id": ALLOWED_USER_ID}),
        "auth_date": str(int(time.time())),
        "hash": "deadbeef" * 8,
    }
    response = client.post("/api/auth/telegram", json={"init_data": urlencode(bad_params)})
    assert response.status_code == 401


def test_non_allowlisted_user_returns_403(client: TestClient) -> None:
    """Valid initData for a user not in allowed_user_ids returns 403."""
    response = client.post(
        "/api/auth/telegram", json={"init_data": _make_init_data(user_id=999999)}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


def test_auth_me_without_token_returns_401(client: TestClient) -> None:
    """GET /api/auth/me with no Authorization header returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_me_with_invalid_token_returns_401(client: TestClient, test_config: Config) -> None:
    """GET /api/auth/me with a garbage Bearer token returns 401."""
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert response.status_code == 401


def test_auth_me_with_valid_token_returns_claims(client: TestClient, test_config: Config) -> None:
    """GET /api/auth/me with a valid JWT returns the claims including the user id."""
    token = create_jwt({"id": ALLOWED_USER_ID}, test_config.jwt_secret)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == ALLOWED_USER_ID
