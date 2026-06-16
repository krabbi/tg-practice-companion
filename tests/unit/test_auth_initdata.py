"""Unit tests for web/auth.py — initData validation and JWT helpers."""

import contextlib
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode

import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from web.auth import create_jwt, decode_jwt, verify_jwt_token, verify_telegram_init_data

BOT_TOKEN = "1234567890:AAFakeTokenForTestingPurposesOnly"
JWT_SECRET = "test-secret-key"


def _make_init_data(
    user_id: int = 999,
    auth_date: int | None = None,
    bot_token: str = BOT_TOKEN,
) -> str:
    """Build a correctly signed initData string for testing."""
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


# ---------------------------------------------------------------------------
# verify_telegram_init_data
# ---------------------------------------------------------------------------


def test_valid_init_data_returns_user_dict() -> None:
    """A hand-computed valid initData passes validation and returns the user dict."""
    init_data = _make_init_data(user_id=999)
    result = verify_telegram_init_data(init_data, BOT_TOKEN)
    assert result is not None
    assert result["id"] == 999


def test_tampered_hash_fails() -> None:
    """initData with a wrong hash is rejected."""
    user = json.dumps({"id": 999, "first_name": "Test"})
    params = {
        "user": user,
        "auth_date": str(int(time.time())),
        "hash": "a" * 64,  # garbage hash
    }
    result = verify_telegram_init_data(urlencode(params), BOT_TOKEN)
    assert result is None


def test_expired_auth_date_fails() -> None:
    """initData older than max_age_seconds is rejected."""
    old_auth_date = int(time.time()) - 90000  # 25 hours ago
    init_data = _make_init_data(auth_date=old_auth_date)
    result = verify_telegram_init_data(init_data, BOT_TOKEN)
    assert result is None


def test_missing_hash_fails() -> None:
    """initData without a hash field is rejected."""
    result = verify_telegram_init_data("user=foo&auth_date=12345", BOT_TOKEN)
    assert result is None


def test_wrong_bot_token_fails() -> None:
    """initData signed with a different bot token is rejected."""
    init_data = _make_init_data(bot_token="other:Token")
    result = verify_telegram_init_data(init_data, BOT_TOKEN)
    assert result is None


def test_custom_max_age_seconds() -> None:
    """Custom max_age_seconds of 0 always rejects (auth_date is in the past)."""
    init_data = _make_init_data()
    result = verify_telegram_init_data(init_data, BOT_TOKEN, max_age_seconds=0)
    assert result is None


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def test_create_jwt_decode_jwt_round_trip() -> None:
    """create_jwt + decode_jwt round-trip preserves the original payload."""
    token = create_jwt({"id": 123456}, JWT_SECRET)
    claims = decode_jwt(token, JWT_SECRET)
    assert claims["id"] == 123456
    assert "exp" in claims


def test_expired_jwt_raises() -> None:
    """decode_jwt raises ExpiredSignatureError for a token that is already expired."""
    token = create_jwt({"id": 1}, JWT_SECRET, expires_in=-1)
    with pytest.raises(jwt.exceptions.ExpiredSignatureError):
        decode_jwt(token, JWT_SECRET)


def test_verify_jwt_token_returns_claims_for_valid_token() -> None:
    """verify_jwt_token returns claims for a valid token."""
    token = create_jwt({"id": 789}, JWT_SECRET)
    result = verify_jwt_token(token, JWT_SECRET)
    assert result is not None
    assert result["id"] == 789


def test_verify_jwt_token_returns_none_for_garbage() -> None:
    """verify_jwt_token returns None for a malformed token."""
    assert verify_jwt_token("not.a.valid.token", JWT_SECRET) is None


def test_verify_jwt_token_returns_none_for_expired() -> None:
    """verify_jwt_token returns None for an expired token (no exception raised)."""
    token = create_jwt({"id": 1}, JWT_SECRET, expires_in=-1)
    assert verify_jwt_token(token, JWT_SECRET) is None


# ---------------------------------------------------------------------------
# get_db_session dependency (unit test with mocks)
# ---------------------------------------------------------------------------


async def test_get_db_session_yields_session() -> None:
    """get_db_session yields the AsyncSession produced by the app's session factory."""
    from web.dependencies import get_db_session

    session = MagicMock(spec=AsyncSession)
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    request = MagicMock()
    request.app.state.session_factory = factory

    gen = get_db_session(request)
    yielded = await gen.__anext__()
    assert yielded is session
    with contextlib.suppress(StopAsyncIteration):
        await gen.__anext__()
