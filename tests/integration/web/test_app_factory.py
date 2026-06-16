"""Integration tests for web/main.py::create_app."""

import pytest
from fastapi.testclient import TestClient

from bot.config import Config
from web.main import create_app

_BASE_CONFIG = {
    "telegram_bot_token": "1234567890:AAFakeTokenForTestingPurposesOnly",
    "anthropic_api_key": "sk-ant-fake-key-for-testing",
    "groq_api_key": "",
    "database_url": "sqlite+aiosqlite:///:memory:",
    "allowed_user_ids": "123456789",
    "monthly_cost_limit_usd": 10.0,
    "analysis_cost_cap_usd": 0.05,
    "default_language": "ru",
    "send_window_start": 6,
    "send_window_end": 22,
    "jwt_secret": "super-secret-test-key",
    "cors_origins": [],
}


@pytest.fixture
def test_config() -> Config:
    """Return a Config with JWT_SECRET set for web tests."""
    return Config.model_validate(_BASE_CONFIG)


def test_create_app_builds(test_config: Config) -> None:
    """create_app with a valid config returns a FastAPI instance."""
    from fastapi import FastAPI

    app = create_app(test_config)
    assert isinstance(app, FastAPI)


def test_health_endpoint(test_config: Config) -> None:
    """GET /api/health returns 200 with {"status": "ok"}."""
    app = create_app(test_config)
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_jwt_secret_raises() -> None:
    """create_app raises ValueError when jwt_secret is empty."""
    config = Config.model_validate({**_BASE_CONFIG, "jwt_secret": ""})
    with pytest.raises(ValueError, match="JWT_SECRET"):
        create_app(config)


def test_config_stored_on_app_state(test_config: Config) -> None:
    """create_app stores the config on app.state.config."""
    app = create_app(test_config)
    assert app.state.config is test_config


def test_cors_wildcard_when_no_origins(test_config: Config) -> None:
    """When cors_origins is empty, CORS is set to wildcard (no credentials)."""
    app = create_app(test_config)
    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
    assert response.headers.get("access-control-allow-origin") == "*"


def test_cors_credentialed_when_origins_set() -> None:
    """When cors_origins is set, CORS allows credentials for those origins."""
    config = Config.model_validate({**_BASE_CONFIG, "cors_origins": "http://app.example.com"})
    app = create_app(config)
    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.headers.get("access-control-allow-origin") == "http://app.example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"
