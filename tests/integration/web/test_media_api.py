"""Integration tests for web/routers/media.py — media upload and motivational-image API."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.practice import MediaAsset
from bot.repositories.media_asset_repository import MediaAssetRepository
from bot.services.storage_service import S3StorageService
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
    "media_max_video_bytes": 262144000,
}

ALLOWED_USER_ID = 123456789
_FAKE_PHOTO_FILE_ID = "AgACAgIAAxkBAAIBfGXfake_photo_file_id"
_FAKE_AUDIO_FILE_ID = "BQACAgIAAxkBAAIBfGXfake_audio_file_id"
_FAKE_VIDEO_FILE_ID = "CgACAgIAAxkBAAIBfGXfake_video_file_id"


def _make_mock_bot() -> MagicMock:
    """Return a mock Bot that captures file_ids for image, audio, and video uploads."""
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

    video_obj = MagicMock()
    video_obj.file_id = _FAKE_VIDEO_FILE_ID
    video_msg = MagicMock()
    video_msg.video = video_obj
    bot.send_video = AsyncMock(return_value=video_msg)

    # Allow the lifespan to close the bot's session without error
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    return bot


def _make_mock_storage() -> S3StorageService:
    """Return a mock S3StorageService."""
    storage = MagicMock(spec=S3StorageService)
    storage.put_object = AsyncMock()
    storage.delete_object = AsyncMock()
    return storage


@pytest.fixture
async def _db():
    """Isolated in-memory SQLite DB; yields (engine, async_sessionmaker)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(_db) -> AsyncClient:
    """AsyncClient with isolated SQLite DB, mocked S3 gateway, and a mocked Bot."""
    _engine, factory = _db

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_BASE_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session
    # Inject mocks before entering the lifespan
    app.state.bot = _make_mock_bot()
    app.state.storage_service = _make_mock_storage()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


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


async def test_upload_image_creates_asset_with_s3_key(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Upload an image → row has telegram_file_id populated, storage_path is an S3 key."""
    fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    files = {"file": ("photo.jpg", io.BytesIO(fake_image), "image/jpeg")}
    data = {"kind": "image"}

    resp = await client.post("/api/media", data=data, files=files, headers=auth_headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "image"
    assert body["mime"] == "image/jpeg"
    assert body["telegram_file_id"] == _FAKE_PHOTO_FILE_ID
    assert body["storage_path"] is not None
    # storage_path is an S3 key (no leading slash, starts with kind/)
    assert body["storage_path"].startswith("image/")
    assert body["storage_path"].endswith(".jpg")
    assert body["id"] is not None


# ---------------------------------------------------------------------------
# Audio upload round-trip
# ---------------------------------------------------------------------------


async def test_upload_audio_creates_asset_with_s3_key(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Upload an audio file → row has telegram_file_id, storage_path is an S3 key."""
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
    assert body["storage_path"].startswith("audio/")


# ---------------------------------------------------------------------------
# Upload size limit
# ---------------------------------------------------------------------------


async def test_upload_just_under_10mb_passes(client: AsyncClient, auth_headers: dict) -> None:
    """Upload of 10 MB - 1 byte is accepted."""
    data_bytes = b"x" * (10 * 1024 * 1024 - 1)
    files = {"file": ("big.jpg", io.BytesIO(data_bytes), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 201


async def test_upload_over_10mb_returns_413(client: AsyncClient, auth_headers: dict) -> None:
    """Upload of a 10 MB + 1 byte image is rejected with 413."""
    data_bytes = b"x" * (10 * 1024 * 1024 + 1)
    files = {"file": ("toobig.jpg", io.BytesIO(data_bytes), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 413
    assert "10 MB" in resp.json()["detail"]


async def test_upload_audio_over_image_limit_passes(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Audio above the 10 MB image cap is accepted (audio cap is 50 MB)."""
    data_bytes = b"x" * (10 * 1024 * 1024 + 1)
    files = {"file": ("big.mp3", io.BytesIO(data_bytes), "audio/mpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "audio"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Video upload round-trip
# ---------------------------------------------------------------------------


async def test_upload_video_creates_asset_with_s3_key(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Upload a small video file → S3 key set, telegram_file_id captured via send_video."""
    fake_video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100
    files = {"file": ("clip.mp4", io.BytesIO(fake_video), "video/mp4")}
    data = {"kind": "video"}

    resp = await client.post("/api/media", data=data, files=files, headers=auth_headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "video"
    assert body["mime"] == "video/mp4"
    assert body["telegram_file_id"] == _FAKE_VIDEO_FILE_ID
    assert body["storage_path"] is not None
    assert body["storage_path"].startswith("video/")
    assert body["storage_path"].endswith(".mp4")
    assert body["id"] is not None


async def test_upload_video_above_audio_limit_passes(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Video above the 50 MB audio cap is accepted (video cap is 250 MB)."""
    data_bytes = b"x" * (50 * 1024 * 1024 + 1)
    files = {"file": ("big.mp4", io.BytesIO(data_bytes), "video/mp4")}
    resp = await client.post(
        "/api/media", data={"kind": "video"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 201


async def test_upload_video_over_250mb_returns_413(client: AsyncClient, auth_headers: dict) -> None:
    """Upload of a 250 MB + 1 byte video is rejected with 413."""
    data_bytes = b"x" * (250 * 1024 * 1024 + 1)
    files = {"file": ("toobig.mp4", io.BytesIO(data_bytes), "video/mp4")}
    resp = await client.post(
        "/api/media", data={"kind": "video"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 413
    assert "250 MB" in resp.json()["detail"]


async def test_upload_video_wrong_mime_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """Upload with a non-video MIME type for kind=video is rejected with 422."""
    files = {"file": ("trick.mp4", io.BytesIO(b"fake"), "application/octet-stream")}
    resp = await client.post(
        "/api/media", data={"kind": "video"}, files=files, headers=auth_headers
    )
    assert resp.status_code == 422
    assert "video/" in resp.json()["detail"]


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


async def test_delete_asset_removes_row(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/media/{id} removes the DB row (S3 delete is mocked)."""
    files = {"file": ("img.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    asset_id = resp.json()["id"]

    resp = await client.delete(f"/api/media/{asset_id}", headers=auth_headers)
    assert resp.status_code == 204

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


# ---------------------------------------------------------------------------
# Presigned URL endpoint
# ---------------------------------------------------------------------------


async def test_get_url_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/media/{id}/url with no token returns 401."""
    response = await client.get(f"/api/media/{uuid.uuid4()}/url")
    assert response.status_code == 401


async def test_get_url_returns_presigned_url(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/media/{id}/url returns a presigned URL and expires_in for an uploaded asset."""
    fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    files = {"file": ("photo.jpg", io.BytesIO(fake_image), "image/jpeg")}
    upload_resp = await client.post(
        "/api/media", data={"kind": "image"}, files=files, headers=auth_headers
    )
    assert upload_resp.status_code == 201
    asset_id = upload_resp.json()["id"]

    # Make the mock storage return a fake presigned URL
    storage: MagicMock = client._transport.app.state.storage_service  # type: ignore[attr-defined]
    storage.generate_presigned_url.return_value = (
        "https://s3.example.com/image/test.jpg?X-Amz-Signature=abc"
    )

    resp = await client.get(f"/api/media/{asset_id}/url", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://s3.example.com/image/test.jpg?X-Amz-Signature=abc"
    assert isinstance(body["expires_in"], int)
    assert body["expires_in"] > 0


async def test_get_url_nonexistent_asset_returns_404(
    client: AsyncClient, auth_headers: dict
) -> None:
    """GET /api/media/{unknown}/url returns 404 for a missing asset."""
    resp = await client.get(f"/api/media/{uuid.uuid4()}/url", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_url_asset_without_storage_path_returns_404(
    client: AsyncClient, auth_headers: dict, _db: tuple
) -> None:
    """GET /api/media/{id}/url returns 404 when storage_path is None."""
    _engine, factory = _db
    asset_id = uuid.uuid4()
    async with factory() as session:
        asset = MediaAsset(
            id=asset_id,
            kind="image",
            storage_path=None,
            telegram_file_id=None,
            mime="image/jpeg",
            user_id=ALLOWED_USER_ID,
        )
        repo = MediaAssetRepository(session)
        await repo.create(asset)
        await session.commit()

    resp = await client.get(f"/api/media/{asset_id}/url", headers=auth_headers)
    assert resp.status_code == 404
