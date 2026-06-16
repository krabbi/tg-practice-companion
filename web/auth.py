"""TMA auth helpers: initData validation and JWT operations (FastAPI-free)."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt


def verify_telegram_init_data(
    init_data: str, bot_token: str, max_age_seconds: int = 86400
) -> dict | None:
    """Validate Telegram Mini App initData; return the parsed user dict or None."""
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    # Build data_check_string: remaining pairs sorted by key, joined with \n
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)
    # Note: key is the literal string "WebAppData"; bot_token is the message
    # (opposite of the Login Widget which uses SHA256(bot_token) as key)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = params.get("auth_date")
    if not auth_date:
        return None
    try:
        if time.time() - int(auth_date) > max_age_seconds:
            return None
    except (ValueError, TypeError):
        return None

    user_str = params.get("user")
    if not user_str:
        return None
    try:
        return json.loads(user_str)
    except json.JSONDecodeError:
        return None


def create_jwt(payload: dict, secret: str, expires_in: int = 86400) -> str:
    """Create a signed HS256 JWT with the given payload and an exp claim."""
    data = {**payload, "exp": int(time.time()) + expires_in}
    return jwt.encode(data, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> dict:
    """Decode and verify an HS256 JWT; raises jwt.exceptions on invalid/expired token."""
    return jwt.decode(token, secret, algorithms=["HS256"])


def verify_jwt_token(token: str, secret: str) -> dict | None:
    """Decode a JWT and return its claims, or None on any decode error."""
    try:
        return decode_jwt(token, secret)
    except Exception:
        return None
