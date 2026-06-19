"""Cross-user isolation tests for all web API endpoints.

Verifies:
- Each endpoint returns only the authenticated user's rows.
- User B gets 404 on GET/PATCH/DELETE of User A's resource.
- Open-registration mode (empty allowed_user_ids): a freshly-provisioned user
  can create and list their own practices without being in an allowlist.
"""

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.journal import JournalEntry
from bot.models.practice import Practice
from bot.services.storage_service import S3StorageService
from web.auth import create_jwt
from web.dependencies import get_db_session
from web.main import create_app

# Open-registration config: empty allowlist lets any JWT holder through.
_OPEN_CONFIG = {
    "telegram_bot_token": "1234567890:AAFakeTokenForTestingPurposesOnly",
    "anthropic_api_key": "sk-ant-fake-key-for-testing",
    "groq_api_key": "",
    "database_url": "sqlite+aiosqlite:///:memory:",
    "allowed_user_ids": [],
    "jwt_secret": "super-secret-test-key",
    "cors_origins": [],
    "send_window_start": 6,
    "send_window_end": 22,
}

USER_A_ID = 111111111
USER_B_ID = 222222222


def _headers(user_id: int) -> dict:
    config = Config.model_validate(_OPEN_CONFIG)
    token = create_jwt({"id": user_id}, config.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def _make_mock_storage() -> S3StorageService:
    storage = MagicMock(spec=S3StorageService)
    storage.put_object = AsyncMock()
    storage.delete_object = AsyncMock()
    return storage


def _make_mock_bot() -> MagicMock:
    bot = MagicMock()
    photo_variant = MagicMock()
    photo_variant.file_id = "fake_photo_file_id"
    photo_msg = MagicMock()
    photo_msg.photo = [photo_variant]
    bot.send_photo = AsyncMock(return_value=photo_msg)

    audio_obj = MagicMock()
    audio_obj.file_id = "fake_audio_file_id"
    audio_msg = MagicMock()
    audio_msg.audio = audio_obj
    bot.send_audio = AsyncMock(return_value=audio_msg)

    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


@pytest.fixture
async def db():
    """Isolated in-memory SQLite DB; yields (engine, sessionmaker)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(db):
    """AsyncClient with open-registration config, mocked S3 and Bot."""
    _engine, factory = db

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_OPEN_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session
    app.state.bot = _make_mock_bot()
    app.state.storage_service = _make_mock_storage()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRACTICE_BODY = {
    "name": "Morning Question",
    "content_type": "question",
    "content": "How do you feel?",
    "periodicity_type": "fixed_times",
    "schedule_times": ["09:00"],
}


async def _create_practice(client: AsyncClient, user_id: int) -> str:
    resp = await client.post("/api/practices", json=_PRACTICE_BODY, headers=_headers(user_id))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_blessing(client: AsyncClient, user_id: int) -> str:
    resp = await client.post(
        "/api/blessings", json={"text": "May you be well"}, headers=_headers(user_id)
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_want(client: AsyncClient, user_id: int) -> str:
    resp = await client.post("/api/wants", json={"text": "learn piano"}, headers=_headers(user_id))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _upload_image(client: AsyncClient, user_id: int) -> str:
    files = {"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=_headers(user_id)
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Practices isolation
# ---------------------------------------------------------------------------


async def test_practices_list_is_scoped_to_user(client: AsyncClient) -> None:
    """User B's GET /api/practices does not include User A's rows."""
    await _create_practice(client, USER_A_ID)

    resp = await client.get("/api/practices", headers=_headers(USER_B_ID))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_practice_get_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on GET /api/practices/{id} owned by User A."""
    pid = await _create_practice(client, USER_A_ID)

    resp = await client.get(f"/api/practices/{pid}", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


async def test_practice_patch_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on PATCH /api/practices/{id} owned by User A."""
    pid = await _create_practice(client, USER_A_ID)

    resp = await client.patch(
        f"/api/practices/{pid}", json={"name": "Hijacked"}, headers=_headers(USER_B_ID)
    )
    assert resp.status_code == 404


async def test_practice_delete_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on DELETE /api/practices/{id} owned by User A."""
    pid = await _create_practice(client, USER_A_ID)

    resp = await client.delete(f"/api/practices/{pid}", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Blessings isolation
# ---------------------------------------------------------------------------


async def test_blessings_list_is_scoped_to_user(client: AsyncClient) -> None:
    """User B's GET /api/blessings does not include User A's rows."""
    await _create_blessing(client, USER_A_ID)

    resp = await client.get("/api/blessings", headers=_headers(USER_B_ID))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_blessing_patch_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on PATCH /api/blessings/{id} owned by User A."""
    bid = await _create_blessing(client, USER_A_ID)

    resp = await client.patch(
        f"/api/blessings/{bid}", json={"text": "Hijacked"}, headers=_headers(USER_B_ID)
    )
    assert resp.status_code == 404


async def test_blessing_delete_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on DELETE /api/blessings/{id} owned by User A."""
    bid = await _create_blessing(client, USER_A_ID)

    resp = await client.delete(f"/api/blessings/{bid}", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Wants isolation
# ---------------------------------------------------------------------------


async def test_wants_list_is_scoped_to_user(client: AsyncClient) -> None:
    """User B's GET /api/wants does not include User A's rows."""
    await _create_want(client, USER_A_ID)

    resp = await client.get("/api/wants", headers=_headers(USER_B_ID))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_want_patch_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on PATCH /api/wants/{id} owned by User A."""
    wid = await _create_want(client, USER_A_ID)

    resp = await client.patch(
        f"/api/wants/{wid}", json={"text": "Hijacked"}, headers=_headers(USER_B_ID)
    )
    assert resp.status_code == 404


async def test_want_delete_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on DELETE /api/wants/{id} owned by User A."""
    wid = await _create_want(client, USER_A_ID)

    resp = await client.delete(f"/api/wants/{wid}", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Media isolation
# ---------------------------------------------------------------------------


async def test_media_list_is_scoped_to_user(client: AsyncClient) -> None:
    """User B's GET /api/media does not include User A's assets."""
    await _upload_image(client, USER_A_ID)

    resp = await client.get("/api/media", headers=_headers(USER_B_ID))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_media_url_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on GET /api/media/{id}/url for User A's asset."""
    asset_id = await _upload_image(client, USER_A_ID)

    resp = await client.get(f"/api/media/{asset_id}/url", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


async def test_media_delete_other_user_returns_404(client: AsyncClient) -> None:
    """User B gets 404 on DELETE /api/media/{id} for User A's asset."""
    asset_id = await _upload_image(client, USER_A_ID)

    resp = await client.delete(f"/api/media/{asset_id}", headers=_headers(USER_B_ID))
    assert resp.status_code == 404


async def test_media_upload_sends_to_acting_user_chat(client: AsyncClient) -> None:
    """Upload uses the acting user's Telegram ID as chat_id, not the first allowlist ID."""
    files = {"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=_headers(USER_A_ID)
    )
    assert resp.status_code == 201

    bot: MagicMock = client._transport.app.state.bot  # type: ignore[attr-defined]
    _, call_kwargs = bot.send_photo.call_args
    assert call_kwargs["chat_id"] == USER_A_ID


# ---------------------------------------------------------------------------
# Journal isolation
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_journal(db) -> dict:
    """Insert one journal entry each for User A and User B."""
    _engine, factory = db
    async with factory() as session:
        practice = Practice(
            name="Test Practice",
            content_type="question",
            content="How are you?",
            periodicity_type="fixed_times",
            schedule_times=["09:00"],
            user_id=USER_A_ID,
        )
        session.add(practice)
        await session.flush()

        entry_a = JournalEntry(
            user_id=USER_A_ID,
            practice_id=practice.id,
            text="User A entry",
            source="text",
            created_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        )
        entry_b = JournalEntry(
            user_id=USER_B_ID,
            practice_id=None,
            text="User B entry",
            source="text",
            created_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        )
        session.add_all([entry_a, entry_b])
        await session.flush()
        await session.commit()

    return {"entry_a_id": entry_a.id, "entry_b_id": entry_b.id}


async def test_journal_list_is_scoped_to_user(client: AsyncClient, seeded_journal: dict) -> None:
    """User A's GET /api/journal returns only their own entries."""
    resp = await client.get("/api/journal", headers=_headers(USER_A_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["text"] == "User A entry"


async def test_journal_get_other_user_entry_returns_404(
    client: AsyncClient, seeded_journal: dict
) -> None:
    """User A gets 404 on GET /api/journal/{id} for User B's entry."""
    entry_b_id = seeded_journal["entry_b_id"]
    resp = await client.get(f"/api/journal/{entry_b_id}", headers=_headers(USER_A_ID))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Open-registration mode
# ---------------------------------------------------------------------------


async def test_open_registration_new_user_can_create_and_list_practices(
    client: AsyncClient,
) -> None:
    """In open-registration mode a freshly-provisioned user can create and list practices."""
    new_user_id = 999888777
    headers = _headers(new_user_id)

    # Create a practice as a brand-new user (no allowlist required)
    resp = await client.post("/api/practices", json=_PRACTICE_BODY, headers=headers)
    assert resp.status_code == 201
    practice_id = resp.json()["id"]

    # List returns exactly that practice
    resp = await client.get("/api/practices", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == practice_id

    # Other users still see an empty list
    resp = await client.get("/api/practices", headers=_headers(USER_A_ID))
    assert resp.status_code == 200
    assert resp.json() == []
