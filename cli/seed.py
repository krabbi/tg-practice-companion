"""CLI: seed operator content from YAML files.

Subcommands:
    practices <yaml>   — upsert Practice rows (idempotent by name).
    blessings <yaml>   — upsert MorningBlessing rows (idempotent by rotation_order).
    images <yaml>      — upload local image files to Telegram, upsert MediaAsset +
                         MotivationalImage rows (idempotent by telegram_file_id).
    audio <yaml>       — upload local audio files to Telegram, upsert MediaAsset rows
                         referenced by Practice rows (idempotent by practice name).

Usage:
    python -m cli.seed practices  content/practices.yaml
    python -m cli.seed blessings  content/blessings.yaml
    python -m cli.seed images     content/images.yaml
    python -m cli.seed audio      content/audio.yaml
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import yaml

from bot.config import get_config
from bot.db import build_session_factory
from bot.models.morning import MorningBlessing, MotivationalImage
from bot.models.practice import MediaAsset, Practice
from bot.repositories.blessing_repository import BlessingRepository
from bot.repositories.image_repository import ImageRepository
from bot.repositories.practice_repository import PracticeRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _warn_anchor_window(
    name: str,
    interval_hours: int,
    anchor_hour: int,
    send_window_start: int,
    send_window_end: int,
) -> None:
    """Warn when no slot produced by anchor_hour + every interval_hours falls in the window."""
    slots = set()
    for h in range(24):
        if (h - anchor_hour) % interval_hours == 0:
            slots.add(h)
    admissible = [h for h in slots if send_window_start <= h < send_window_end]
    if not admissible:
        logger.warning(
            "Practice %r: interval_hours=%d anchor_hour=%d yields NO slot inside "
            "[%02d:00, %02d:00) — this practice will never fire.",
            name,
            interval_hours,
            anchor_hour,
            send_window_start,
            send_window_end,
        )


# ---------------------------------------------------------------------------
# practices subcommand
# ---------------------------------------------------------------------------


def _parse_practice(row: dict, user_id: int) -> tuple[Practice, dict | None]:
    """Parse one YAML row into a Practice and optional media metadata dict."""
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
        user_id=user_id,
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

    with yaml_path.open(encoding="utf-8") as f:
        rows: list[dict] = yaml.safe_load(f)

    if not rows:
        logger.info("No practices found in %s", yaml_path)
        return

    if not config.allowed_user_ids:
        logger.error("ALLOWED_USER_IDS is empty — cannot determine user_id for seeding")
        sys.exit(1)
    seed_user_id = config.allowed_user_ids[0]

    async with session_factory() as session:
        repo = PracticeRepository(session)

        for row in rows:
            name: str = row["name"]

            # Anchor-window validation for every_n_hours practices
            if (
                row.get("periodicity_type") == "every_n_hours"
                and row.get("interval_hours") is not None
            ):
                _warn_anchor_window(
                    name=name,
                    interval_hours=row["interval_hours"],
                    anchor_hour=row.get("anchor_hour", 0),
                    send_window_start=config.send_window_start,
                    send_window_end=config.send_window_end,
                )

            practice, media_dict = _parse_practice(row, seed_user_id)
            existing = await repo.get_by_name(name, seed_user_id)

            asset_id: uuid.UUID | None = None
            if media_dict is not None:
                if existing is not None and existing.media_asset_id is not None:
                    existing_asset = await repo.get_media_asset_by_id(
                        existing.media_asset_id, seed_user_id
                    )
                    if existing_asset is not None:
                        existing_asset.telegram_file_id = media_dict["telegram_file_id"]
                        existing_asset.mime = media_dict["mime"]
                        await repo.save_media_asset(existing_asset)
                        asset_id = existing_asset.id
                        logger.info("Updated media_asset for practice %r", name)
                else:
                    asset = MediaAsset(
                        id=uuid.uuid4(),
                        user_id=seed_user_id,
                        kind=media_dict["kind"],
                        telegram_file_id=media_dict["telegram_file_id"],
                        mime=media_dict["mime"],
                    )
                    await repo.save_media_asset(asset)
                    asset_id = asset.id
                    logger.info("Created media_asset for practice %r", name)

            if existing is not None:
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


# ---------------------------------------------------------------------------
# blessings subcommand
# ---------------------------------------------------------------------------


async def seed_blessings(yaml_path: Path) -> None:
    """Upsert morning blessings from the given YAML file (idempotent by rotation_order)."""
    config = get_config()
    session_factory = build_session_factory(config.database_url)

    with yaml_path.open(encoding="utf-8") as f:
        rows: list[dict] = yaml.safe_load(f)

    if not rows:
        logger.info("No blessings found in %s", yaml_path)
        return

    if not config.allowed_user_ids:
        logger.error("ALLOWED_USER_IDS is empty — cannot determine user_id for seeding")
        sys.exit(1)
    seed_user_id = config.allowed_user_ids[0]

    async with session_factory() as session:
        repo = BlessingRepository(session)

        for row in rows:
            rotation_order: int = row["rotation_order"]
            text: str = row["text"]
            active: bool = row.get("active", True)

            existing = await repo.get_by_rotation_order(rotation_order, seed_user_id)
            if existing is not None:
                existing.text = text
                existing.active = active
                await repo.save(existing)
                logger.info("Updated blessing rotation_order=%d", rotation_order)
            else:
                blessing = MorningBlessing(
                    id=uuid.uuid4(),
                    user_id=seed_user_id,
                    text=text,
                    rotation_order=rotation_order,
                    active=active,
                )
                await repo.save(blessing)
                logger.info("Created blessing rotation_order=%d", rotation_order)

        await session.commit()

    logger.info("Seeding complete: %d blessings processed", len(rows))


# ---------------------------------------------------------------------------
# images subcommand (upload + upsert MotivationalImage)
# ---------------------------------------------------------------------------


async def seed_images(yaml_path: Path, *, bot: object | None = None) -> None:
    """Upload local image files to Telegram and upsert MediaAsset + MotivationalImage rows.

    Each YAML entry must have a `local_path` field pointing to the image file.
    The file is uploaded to the first allowed user via bot.send_photo.
    Re-runs are idempotent: files already uploaded (same local_path) are re-uploaded
    and the media_asset row updated.

    `bot` may be injected for testing (skips Bot construction).
    """
    from aiogram import Bot
    from aiogram.types import FSInputFile

    config = get_config()
    session_factory = build_session_factory(config.database_url)

    with yaml_path.open(encoding="utf-8") as f:
        rows: list[dict] = yaml.safe_load(f)

    if not rows:
        logger.info("No images found in %s", yaml_path)
        return

    if not config.allowed_user_ids:
        logger.error("ALLOWED_USER_IDS is empty — cannot upload files to Telegram")
        sys.exit(1)

    upload_chat_id = config.allowed_user_ids[0]
    own_bot = bot is None
    if own_bot:
        bot = Bot(token=config.telegram_bot_token)

    try:
        async with session_factory() as session:
            practice_repo = PracticeRepository(session)
            image_repo = ImageRepository(session)

            for row in rows:
                local_path = Path(row["local_path"])
                mime: str = row.get("mime", "image/jpeg")
                active: bool = row.get("active", True)

                if not local_path.exists():
                    logger.error("Image file not found: %s — skipping", local_path)
                    continue

                logger.info("Uploading %s …", local_path)
                input_file = FSInputFile(local_path)
                msg = await bot.send_photo(chat_id=upload_chat_id, photo=input_file)  # type: ignore[union-attr]
                if msg.photo is None:
                    logger.error("Upload returned no photo for %s — skipping", local_path)
                    continue
                telegram_file_id: str = msg.photo[-1].file_id
                logger.info("Uploaded %s → file_id=%s", local_path, telegram_file_id)

                # Upsert media_asset
                existing_asset = await practice_repo.get_media_asset_by_telegram_file_id(
                    telegram_file_id
                )
                if existing_asset is not None:
                    existing_asset.mime = mime
                    await practice_repo.save_media_asset(existing_asset)
                    asset_id = existing_asset.id
                    logger.info("Updated existing media_asset id=%s", asset_id)
                else:
                    asset = MediaAsset(
                        id=uuid.uuid4(),
                        user_id=upload_chat_id,
                        kind="image",
                        telegram_file_id=telegram_file_id,
                        mime=mime,
                        storage_path=None,
                    )
                    await practice_repo.save_media_asset(asset)
                    asset_id = asset.id
                    logger.info("Created media_asset id=%s", asset_id)

                # Upsert motivational_image row
                existing_img = await image_repo.get_by_media_asset_id(asset_id, upload_chat_id)
                if existing_img is not None:
                    existing_img.active = active
                    await image_repo.save(existing_img)
                    logger.info("Updated motivational_image for asset %s", asset_id)
                else:
                    motivational_img = MotivationalImage(
                        id=uuid.uuid4(),
                        user_id=upload_chat_id,
                        media_asset_id=asset_id,
                        active=active,
                    )
                    await image_repo.save(motivational_img)
                    logger.info("Created motivational_image for asset %s", asset_id)

            await session.commit()
    finally:
        if own_bot:
            await bot.session.close()  # type: ignore[union-attr]

    logger.info("Seeding complete: %d images processed", len(rows))


# ---------------------------------------------------------------------------
# audio subcommand (upload + upsert MediaAsset referenced by Practice)
# ---------------------------------------------------------------------------


async def seed_audio(yaml_path: Path, *, bot: object | None = None) -> None:
    """Upload local audio files to Telegram and upsert MediaAsset rows.

    Each YAML entry must have `name` (practice name) and `local_path`.
    The practice row must exist (seed practices first).
    Re-runs are idempotent: the media_asset row is updated in place.

    `bot` may be injected for testing (skips Bot construction).
    """
    from aiogram import Bot
    from aiogram.types import FSInputFile

    config = get_config()
    session_factory = build_session_factory(config.database_url)

    with yaml_path.open(encoding="utf-8") as f:
        rows: list[dict] = yaml.safe_load(f)

    if not rows:
        logger.info("No audio entries found in %s", yaml_path)
        return

    if not config.allowed_user_ids:
        logger.error("ALLOWED_USER_IDS is empty — cannot upload files to Telegram")
        sys.exit(1)

    upload_chat_id = config.allowed_user_ids[0]
    own_bot = bot is None
    if own_bot:
        bot = Bot(token=config.telegram_bot_token)

    try:
        async with session_factory() as session:
            repo = PracticeRepository(session)

            for row in rows:
                name: str = row["name"]
                local_path = Path(row["local_path"])
                mime: str = row.get("mime", "audio/mpeg")

                if not local_path.exists():
                    logger.error("Audio file not found: %s — skipping", local_path)
                    continue

                practice = await repo.get_by_name(name, upload_chat_id)
                if practice is None:
                    logger.error("Practice %r not found — seed practices first, then audio", name)
                    continue

                logger.info("Uploading %s …", local_path)
                input_file = FSInputFile(local_path)
                msg = await bot.send_audio(chat_id=upload_chat_id, audio=input_file)  # type: ignore[union-attr]
                if msg.audio is None:
                    logger.error("Upload returned no audio for %s — skipping", local_path)
                    continue
                telegram_file_id: str = msg.audio.file_id
                logger.info("Uploaded %s → file_id=%s", local_path, telegram_file_id)

                # Upsert media_asset
                if practice.media_asset_id is not None:
                    existing_asset = await repo.get_media_asset_by_id(
                        practice.media_asset_id, upload_chat_id
                    )
                    if existing_asset is not None:
                        existing_asset.telegram_file_id = telegram_file_id
                        existing_asset.mime = mime
                        await repo.save_media_asset(existing_asset)
                        logger.info("Updated media_asset for practice %r", name)
                    else:
                        asset = MediaAsset(
                            id=uuid.uuid4(),
                            user_id=upload_chat_id,
                            kind="audio",
                            telegram_file_id=telegram_file_id,
                            mime=mime,
                            storage_path=None,
                        )
                        await repo.save_media_asset(asset)
                        practice.media_asset_id = asset.id
                        await repo.save(practice)
                        logger.info("Created media_asset for practice %r", name)
                else:
                    asset = MediaAsset(
                        id=uuid.uuid4(),
                        user_id=upload_chat_id,
                        kind="audio",
                        telegram_file_id=telegram_file_id,
                        mime=mime,
                        storage_path=None,
                    )
                    await repo.save_media_asset(asset)
                    practice.media_asset_id = asset.id
                    await repo.save(practice)
                    logger.info("Created media_asset for practice %r", name)

            await session.commit()
    finally:
        if own_bot:
            await bot.session.close()  # type: ignore[union-attr]

    logger.info("Seeding complete: %d audio entries processed", len(rows))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_SUBCOMMANDS = {
    "practices": seed_practices,
    "blessings": seed_blessings,
    "images": seed_images,
    "audio": seed_audio,
}


def main() -> None:
    """Entry point: python -m cli.seed <subcommand> <yaml_path>."""
    if len(sys.argv) < 3 or sys.argv[1] not in _SUBCOMMANDS:
        cmds = " | ".join(_SUBCOMMANDS)
        print(f"Usage: python -m cli.seed [{cmds}] <yaml_path>", file=sys.stderr)
        sys.exit(1)

    subcommand = sys.argv[1]
    yaml_path = Path(sys.argv[2])
    if not yaml_path.exists():
        print(f"File not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_SUBCOMMANDS[subcommand](yaml_path))


if __name__ == "__main__":
    main()
