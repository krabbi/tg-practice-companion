"""Unit tests for TimezoneService.set_timezone."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.exceptions import TimezoneError
from bot.models.user import User
from bot.repositories.user_repository import UserRepository
from bot.services.timezone_service import TimezoneService


def make_user(timezone: str = "UTC") -> User:
    """Return a minimal User instance for testing."""
    u = User()
    u.telegram_id = 111222333
    u.timezone = timezone
    u.tz_changed_at = None
    u.language = "ru"
    return u


def make_service(
    user: User | None = None,
) -> tuple[TimezoneService, MagicMock, MagicMock]:
    """Return (service, mock_session, mock_user_repo)."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    user_repo = MagicMock(spec=UserRepository)
    user_repo.get_by_telegram_id = AsyncMock(return_value=user)
    user_repo.save = AsyncMock(side_effect=lambda u: u)

    svc = TimezoneService(session=session, user_repo=user_repo)
    return svc, session, user_repo


# ---------------------------------------------------------------------------
# Invalid timezone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_timezone_invalid_zone_raises() -> None:
    """set_timezone raises TimezoneError for an unknown IANA zone."""
    svc, session, user_repo = make_service()

    with pytest.raises(TimezoneError, match="Invalid IANA timezone"):
        await svc.set_timezone(111222333, "Not/AZone")

    # DB must never be touched for an invalid zone
    user_repo.get_by_telegram_id.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_timezone_empty_string_raises() -> None:
    """set_timezone raises TimezoneError for an empty string."""
    svc, session, _ = make_service()

    with pytest.raises(TimezoneError):
        await svc.set_timezone(111222333, "")


# ---------------------------------------------------------------------------
# User not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_timezone_user_not_found_raises() -> None:
    """set_timezone raises TimezoneError when the user row does not exist."""
    svc, session, user_repo = make_service(user=None)

    with pytest.raises(TimezoneError, match="not found"):
        await svc.set_timezone(111222333, "Europe/Berlin")

    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Successful update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_timezone_persists_new_zone() -> None:
    """set_timezone updates user.timezone and calls commit."""
    user = make_user("UTC")
    svc, session, user_repo = make_service(user=user)

    fixed_now = datetime(2026, 6, 10, 8, 0, tzinfo=UTC)
    with patch("bot.services.timezone_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        returned = await svc.set_timezone(111222333, "Europe/Berlin")

    assert returned is user
    assert user.timezone == "Europe/Berlin"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_timezone_stamps_tz_changed_at() -> None:
    """set_timezone stamps tz_changed_at to the current UTC datetime."""
    user = make_user("UTC")
    svc, session, _ = make_service(user=user)

    fixed_now = datetime(2026, 6, 10, 12, 30, tzinfo=UTC)
    with patch("bot.services.timezone_service.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        await svc.set_timezone(111222333, "America/New_York")

    assert user.tz_changed_at == fixed_now


@pytest.mark.asyncio
async def test_set_timezone_calls_repo_save() -> None:
    """set_timezone calls user_repo.save with the updated user."""
    user = make_user("UTC")
    svc, _, user_repo = make_service(user=user)

    with patch("bot.services.timezone_service.datetime"):
        await svc.set_timezone(111222333, "Asia/Tokyo")

    user_repo.save.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_set_timezone_commit_called_exactly_once() -> None:
    """set_timezone calls session.commit() exactly once per successful call."""
    user = make_user("UTC")
    svc, session, _ = make_service(user=user)

    with patch("bot.services.timezone_service.datetime"):
        await svc.set_timezone(111222333, "Pacific/Auckland")

    session.commit.assert_awaited_once()
