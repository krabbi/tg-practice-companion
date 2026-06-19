"""Unit tests for S3StorageService and build_s3_client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.storage_service import S3StorageService, build_s3_client


def _make_config(**overrides):
    """Return a namespace with S3 config fields."""
    defaults = {
        "s3_endpoint_url": "https://s3.example.com",
        "s3_region": "us-west-004",
        "s3_bucket": "test-bucket",
        "s3_access_key_id": "key-id",
        "s3_secret_access_key": "secret",
        "s3_presign_expiry_seconds": 900,
        "media_max_image_bytes": 10 * 1024 * 1024,
        "media_max_audio_bytes": 50 * 1024 * 1024,
    }
    defaults.update(overrides)

    cfg = MagicMock()
    for k, v in defaults.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# build_s3_client
# ---------------------------------------------------------------------------


def test_build_s3_client_raises_when_endpoint_missing():
    cfg = _make_config(s3_endpoint_url="")
    with pytest.raises(ValueError, match="S3_ENDPOINT_URL"):
        build_s3_client(cfg)


def test_build_s3_client_raises_when_region_missing():
    cfg = _make_config(s3_region="")
    with pytest.raises(ValueError, match="S3_REGION"):
        build_s3_client(cfg)


def test_build_s3_client_raises_when_bucket_missing():
    cfg = _make_config(s3_bucket="")
    with pytest.raises(ValueError, match="S3_BUCKET"):
        build_s3_client(cfg)


def test_build_s3_client_raises_when_access_key_missing():
    cfg = _make_config(s3_access_key_id="")
    with pytest.raises(ValueError, match="S3_ACCESS_KEY_ID"):
        build_s3_client(cfg)


def test_build_s3_client_raises_when_secret_missing():
    cfg = _make_config(s3_secret_access_key="")
    with pytest.raises(ValueError, match="S3_SECRET_ACCESS_KEY"):
        build_s3_client(cfg)


def test_build_s3_client_raises_lists_all_missing():
    cfg = _make_config(s3_access_key_id="", s3_secret_access_key="")
    with pytest.raises(ValueError, match="S3_ACCESS_KEY_ID"):
        build_s3_client(cfg)


@patch("bot.services.storage_service.boto3.client")
@patch("bot.services.storage_service.BotocoreConfig")
def test_build_s3_client_passes_correct_args(mock_botocore_cfg, mock_boto_client):
    cfg = _make_config()
    botocore_instance = MagicMock()
    mock_botocore_cfg.return_value = botocore_instance

    build_s3_client(cfg)

    mock_botocore_cfg.assert_called_once_with(signature_version="s3v4")
    mock_boto_client.assert_called_once_with(
        "s3",
        endpoint_url=cfg.s3_endpoint_url,
        region_name=cfg.s3_region,
        aws_access_key_id=cfg.s3_access_key_id,
        aws_secret_access_key=cfg.s3_secret_access_key,
        config=botocore_instance,
    )


# ---------------------------------------------------------------------------
# S3StorageService.from_config
# ---------------------------------------------------------------------------


@patch("bot.services.storage_service.build_s3_client")
def test_from_config_constructs_service(mock_build):
    cfg = _make_config()
    fake_client = MagicMock()
    mock_build.return_value = fake_client

    svc = S3StorageService.from_config(cfg)

    mock_build.assert_called_once_with(cfg)
    assert svc._client is fake_client
    assert svc._bucket == cfg.s3_bucket
    assert svc._default_expiry == cfg.s3_presign_expiry_seconds


# ---------------------------------------------------------------------------
# put_object
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_object_calls_client_with_content_type():
    client = MagicMock()
    svc = S3StorageService(client, "my-bucket")

    await svc.put_object("folder/key.ogg", b"audio", "audio/ogg")

    client.put_object.assert_called_once_with(
        Bucket="my-bucket", Key="folder/key.ogg", Body=b"audio", ContentType="audio/ogg"
    )


@pytest.mark.asyncio
async def test_put_object_omits_content_type_when_none():
    client = MagicMock()
    svc = S3StorageService(client, "my-bucket")

    await svc.put_object("k", b"data", None)

    client.put_object.assert_called_once_with(Bucket="my-bucket", Key="k", Body=b"data")


@pytest.mark.asyncio
async def test_put_object_runs_via_to_thread():
    """Verify the blocking call is dispatched through asyncio.to_thread."""
    client = MagicMock()
    svc = S3StorageService(client, "bucket")

    with patch(
        "bot.services.storage_service.asyncio.to_thread", new_callable=AsyncMock
    ) as mock_to_thread:
        await svc.put_object("k", b"d", "image/jpeg")

        assert mock_to_thread.called
        args = mock_to_thread.call_args[0]
        assert args[0] is client.put_object


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_calls_client():
    client = MagicMock()
    svc = S3StorageService(client, "bucket")

    await svc.delete_object("some/key")

    client.delete_object.assert_called_once_with(Bucket="bucket", Key="some/key")


@pytest.mark.asyncio
async def test_delete_object_runs_via_to_thread():
    client = MagicMock()
    svc = S3StorageService(client, "bucket")

    with patch(
        "bot.services.storage_service.asyncio.to_thread", new_callable=AsyncMock
    ) as mock_to_thread:
        await svc.delete_object("k")

        assert mock_to_thread.called
        args = mock_to_thread.call_args[0]
        assert args[0] is client.delete_object


# ---------------------------------------------------------------------------
# generate_presigned_url
# ---------------------------------------------------------------------------


def test_generate_presigned_url_uses_default_expiry():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://presigned.example.com/key"
    svc = S3StorageService(client, "bucket", default_expiry=600)

    url = svc.generate_presigned_url("path/to/file.jpg")

    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "bucket", "Key": "path/to/file.jpg"},
        ExpiresIn=600,
    )
    assert url == "https://presigned.example.com/key"


def test_generate_presigned_url_overrides_expiry():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://presigned.example.com/key"
    svc = S3StorageService(client, "bucket", default_expiry=600)

    svc.generate_presigned_url("path/file", expires_in=300)

    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "bucket", "Key": "path/file"},
        ExpiresIn=300,
    )
