"""S3-compatible object storage gateway (Backblaze B2 / AWS-portable)."""

import asyncio

import boto3
from botocore.config import Config as BotocoreConfig

from bot.config import Config


def build_s3_client(config: Config):  # type: ignore[return]
    """Build a boto3 S3 client from *config*.

    Raises ValueError if any required S3 variable is empty — call only from web/CLI
    wiring, never at bot import time.
    """
    missing = [
        name
        for name, val in [
            ("S3_ENDPOINT_URL", config.s3_endpoint_url),
            ("S3_REGION", config.s3_region),
            ("S3_BUCKET", config.s3_bucket),
            ("S3_ACCESS_KEY_ID", config.s3_access_key_id),
            ("S3_SECRET_ACCESS_KEY", config.s3_secret_access_key),
        ]
        if not val
    ]
    if missing:
        raise ValueError(f"S3 config vars not set: {', '.join(missing)}")

    return boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint_url,
        region_name=config.s3_region,
        aws_access_key_id=config.s3_access_key_id,
        aws_secret_access_key=config.s3_secret_access_key,
        config=BotocoreConfig(signature_version="s3v4"),
    )


class S3StorageService:
    """Async gateway for S3-compatible object storage."""

    def __init__(self, client, bucket: str, default_expiry: int = 900) -> None:
        self._client = client
        self._bucket = bucket
        self._default_expiry = default_expiry

    @classmethod
    def from_config(cls, config: Config) -> "S3StorageService":
        """Construct from *config*, raising ValueError if required S3 vars are missing."""
        client = build_s3_client(config)
        return cls(client, config.s3_bucket, config.s3_presign_expiry_seconds)

    async def put_object(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Upload *data* at *key* in the configured bucket."""
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type is not None:
            kwargs["ContentType"] = content_type
        await asyncio.to_thread(self._client.put_object, **kwargs)

    async def delete_object(self, key: str) -> None:
        """Delete the object at *key* from the configured bucket."""
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    def generate_presigned_url(self, key: str, expires_in: int | None = None) -> str:
        """Return a presigned GET URL for *key*, valid for *expires_in* seconds."""
        expiry = expires_in if expires_in is not None else self._default_expiry
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )
        return url
