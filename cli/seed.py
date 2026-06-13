"""CLI command: seed practices from a YAML file.

Usage:
    python -m cli.seed practices content/practices.yaml

The upsert is idempotent: a practice row is identified by its name.
Audio/image practices upsert a media_assets row and link it via media_asset_id.
storage_path stays null in Stage 1; telegram_file_id is populated here.
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import yaml

from bot.config import get_config
from bot.db import build_session_factory
from bot.models.practice import MediaAsset, Practice
from bot.repositories.practice_repository import PracticeRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_practice(row: dict) -> tuple[Practice, dict | None]:
    """Parse one YAML row into a Practice and optional media metadata dict.

    Returns (practice, media_dict) where media_dict is non-None for audio/image rows.
    """
    content_type: str = row["content_type"]
    media_dict: dict | None = None

    if content_type in ("audio", "image"):
        media_dict = {
            "kind": content_type,
            "telegram_file_id": row.get("telegram_file_id"),
            "mime": row.get("mime"),
        }

    practice = Practice(
        id=uuid.uuid4(),
        name=row["name"],
        content_type=content_type,
        content=row.get("content"),
        periodicity_type=row["periodicity_type"],
        interval_hours=row.get("interval_hours"),
        schedule_times=row.get("schedule_times"),
        anchor_hour=row.get("anchor_hour", 0),
        anchor_minute=row.get("anchor_minute", 0),
        active=row.get("active", True),
        sort_order=row.get("sort_order", 0),
    )
    return practice, media_dict


async def seed_practices(yaml_path: Path) -> None:
    """Upsert practices from the given YAML file into the database."""
    config = get_config()
    session_factory = build_session_factory(config.database_url)

    with yaml_path.open() as f:
        rows: list[dict] = yaml.safe_load(f)

    if not rows:
        logger.info("No practices found in %s", yaml_path)
        return

    async with session_factory() as session:
        repo = PracticeRepository(session)

        for row in rows:
            name: str = row["name"]
            practice, media_dict = _parse_practice(row)

            existing = await repo.get_by_name(name)

            # Upsert media asset first (for audio/image)
            asset_id: uuid.UUID | None = None
            if media_dict is not None:
                if existing is not None and existing.media_asset_id is not None:
                    # Update existing asset
                    existing_asset = await repo.get_media_asset_by_id(existing.media_asset_id)
                    if existing_asset is not None:
                        existing_asset.telegram_file_id = media_dict["telegram_file_id"]
                        existing_asset.mime = media_dict["mime"]
                        await repo.save_media_asset(existing_asset)
                        asset_id = existing_asset.id
                        logger.info("Updated media_asset for practice %r", name)
                else:
                    asset = MediaAsset(
                        id=uuid.uuid4(),
                        kind=media_dict["kind"],
                        telegram_file_id=media_dict["telegram_file_id"],
                        mime=media_dict["mime"],
                    )
                    await repo.save_media_asset(asset)
                    asset_id = asset.id
                    logger.info("Created media_asset for practice %r", name)

            if existing is not None:
                # Update the existing practice in place
                existing.content_type = practice.content_type
                existing.content = practice.content
                existing.periodicity_type = practice.periodicity_type
                existing.interval_hours = practice.interval_hours
                existing.schedule_times = practice.schedule_times
                existing.anchor_hour = practice.anchor_hour
                existing.anchor_minute = practice.anchor_minute
                existing.active = practice.active
                existing.sort_order = practice.sort_order
                if asset_id is not None:
                    existing.media_asset_id = asset_id
                await repo.save(existing)
                logger.info("Updated practice %r", name)
            else:
                practice.media_asset_id = asset_id
                await repo.save(practice)
                logger.info("Created practice %r", name)

        await session.commit()

    logger.info("Seeding complete: %d practices processed", len(rows))


def main() -> None:
    """Entry point: python -m cli.seed practices <path>."""
    if len(sys.argv) < 3 or sys.argv[1] != "practices":
        print("Usage: python -m cli.seed practices <yaml_path>", file=sys.stderr)
        sys.exit(1)

    yaml_path = Path(sys.argv[2])
    if not yaml_path.exists():
        print(f"File not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed_practices(yaml_path))


if __name__ == "__main__":
    main()
