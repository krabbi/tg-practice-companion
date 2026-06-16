"""Integration tests for web/routers/media.py — media upload and motivational-image API."""

import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
_FAKE_PHOTO_FILE_ID = "AgACAgIAAxkBAAIBfGXfake_photo_file_id"
_FAKE_AUDIO_FILE_ID = "BQACAgIAAxkBAAIBfGXfake_audio_file_id"


def _make_mock_bot() -> MagicMock:
    """Return a mock Bot that captures file_ids for image and audio uploads."""
    bot = MagicMock()
    photo_variant = MagicMock()
    photo_variant.file_id = _FAKE_PHOTO_FILE_ID
    photo_msg = MagicMock()
    photo_msg.photo = [photo_variant]
    bot.send_photo = AsyncMock(return_value=photo_msg)

    audio_obj = MagicMock()
    audio_obj.file_id = _FAKE_AUDIO_FILE_ID
    audio_msg = MagicMock()
    audio_msg.audio = audio_obj
    bot.send_audio = AsyncMock(return_value=audio_msg)

    # Allow the lifespan to close the bot's session without error
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


@pytest.fixture
async def client(tmp_path: Path) -> AsyncClient:
    """AsyncClient with isolated SQLite DB, temp media dir, and a mocked Bot."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate({**_BASE_CONFIG, "media_storage_dir": str(tmp_path)})
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session
    # Inject mock Bot before entering the lifespan so own_bot=False in lifespan
    app.state.bot = _make_mock_bot()

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


async def test_upload_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/media with no token returns 401."""
    data = {"kind": "image"}
    files = {"file": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    response = await client.post("/api/media", data=data, files=files)
    assert response.status_code == 401


async def test_list_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/media with no token returns 401."""
    response = await client.get("/api/media")
    assert response.status_code == 401


async def test_delete_without_token_returns_401(client: AsyncClient) -> None:
    """DELETE /api/media/{id} with no token returns 401."""
    response = await client.delete(f"/api/media/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_motivational_image_without_token_returns_401(client: AsyncClient) -> None:
    """POST /api/motivational-images with no token returns 401."""
    response = await client.post(
        "/api/motivational-images", json={"media_asset_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Image upload round-trip
# ---------------------------------------------------------------------------


async def test_upload_image_creates_asset_with_file_id(
    client: AsyncClient, auth_headers: dict, tmp_path: Path
) -> None:
    """Upload an image → row has telegram_file_id populated, storage_path set, correct kind/mime."""
    fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like bytes
    files = {"file": ("photo.jpg", io.BytesIO(fake_image), "image/jpeg")}
    data = {"kind": "image"}

    resp = await client.post("/api/media", data=data, files=files, headers=auth_headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "image"
    assert body["mime"] == "image/jpeg"
    assert body["telegram_file_id"] == _FAKE_PHOTO_FILE_ID
    assert body["storage_path"] is not None
    assert Path(body["storage_path"]).exists()
    assert body["id"] is not None


# ---------------------------------------------------------------------------
# Audio upload round-trip
# ---------------------------------------------------------------------------


async def test_upload_audio_creates_asset_with_file_id(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Upload an audio file → row has telegram_file_id, storage_path, kind=audio."""
    fake_audio = b"ID3" + b"\x00" * 100
    files = {"file": ("track.mp3", io.BytesIO(fake_audio), "audio/mpeg")}
    data = {"kind": "audio"}

    resp = await client.post("/api/media", data=data, files=files, headers=auth_headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "audio"
    assert body["mime"] == "audio/mpeg"
    assert body["telegram_file_id"] == _FAKE_AUDIO_FILE_ID
    assert body["storage_path"] is not None


# ---------------------------------------------------------------------------
# List media
# ---------------------------------------------------------------------------


async def test_list_returns_uploaded_assets(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/media returns all uploaded assets."""
    for i in range(2):
        files = {"file": (f"img{i}.jpg", io.BytesIO(b"fake"), "image/jpeg")}
        await client.post("/api/media", data={"kind": "image"}, files=files, headers=auth_headers)

    resp = await client.get("/api/media", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_filter_by_kind(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/media?kind=audio returns only audio assets."""
    await client.post(
        "/api/media",
        data={"kind": "image"},
        files={"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")},
        headers=auth_headers,
    )
    await client.post(
        "/api/media",
        data={"kind": "audio"},
        files={"file": ("track.mp3", io.BytesIO(b"fake"), "audio/mpeg")},
        headers=auth_headers,
    )

    resp = await client.get("/api/media?kind=audio", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["kind"] == "audio"


# ---------------------------------------------------------------------------
# Delete media
# ---------------------------------------------------------------------------


async def test_delete_asset_removes_row_and_file(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/media/{id} removes the row and the file on disk."""
    files = {"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    asset_id = resp.json()["id"]
    storage_path = Path(resp.json()["storage_path"])

    resp = await client.delete(f"/api/media/{asset_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert not storage_path.exists()

    # List should be empty
    resp = await client.get("/api/media", headers=auth_headers)
    assert resp.json() == []


async def test_delete_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/media/{unknown} returns 404."""
    resp = await client.delete(f"/api/media/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Motivational-image pool
# ---------------------------------------------------------------------------


async def test_create_motivational_image_references_asset(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /api/motivational-images creates a pool entry referencing the asset."""
    files = {"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    upload_resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    asset_id = upload_resp.json()["id"]

    resp = await client.post(
        "/api/motivational-images",
        json={"media_asset_id": asset_id, "active": True},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["media_asset_id"] == asset_id
    assert body["active"] is True
    assert body["id"] is not None


async def test_motivational_image_nonexistent_asset_returns_400(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /api/motivational-images with unknown asset_id returns 400."""
    resp = await client.post(
        "/api/motivational-images",
        json={"media_asset_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_motivational_image_wrong_kind_returns_400(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /api/motivational-images with an audio asset returns 400."""
    files = {"file": ("track.mp3", io.BytesIO(b"fake"), "audio/mpeg")}
    upload_resp = await client.post(
        "/api/media", data={"kind": "audio"}, files=files, headers=auth_headers
    )
    asset_id = upload_resp.json()["id"]

    resp = await client.post(
        "/api/motivational-images",
        json={"media_asset_id": asset_id},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "image" in resp.json()["detail"]
