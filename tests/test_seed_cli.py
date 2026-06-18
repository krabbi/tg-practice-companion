"""Tests for cli/seed.py — practices, blessings, images, audio seeding.

Uses the aiosqlite in-memory db_session fixture from conftest.
Media upload tests inject a mocked Bot to avoid real Telegram API calls.
"""

import logging
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.models.practice import MediaAsset, Practice
from bot.repositories.blessing_repository import BlessingRepository
from bot.repositories.image_repository import ImageRepository
from bot.repositories.practice_repository import PracticeRepository
from cli.seed import (
    _warn_anchor_window,
    seed_audio,
    seed_blessings,
    seed_images,
    seed_practices,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRACTICES_EXAMPLE = Path(__file__).parent.parent / "content" / "practices.example.yaml"


def _make_photo_msg(file_id: str) -> MagicMock:
    """Return a fake Message with a photo array (largest last)."""
    photo_size = MagicMock()
    photo_size.file_id = file_id
    msg = MagicMock()
    msg.photo = [photo_size]
    return msg


def _make_audio_msg(file_id: str) -> MagicMock:
    """Return a fake Message with an audio object."""
    audio = MagicMock()
    audio.file_id = file_id
    msg = MagicMock()
    msg.audio = audio
    return msg


def _make_mock_bot(send_photo_file_id: str = "photo_file_id_123") -> MagicMock:
    """Return a mock Bot whose send_photo returns a fake message."""
    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock(return_value=_make_photo_msg(send_photo_file_id))
    mock_bot.send_audio = AsyncMock(return_value=_make_audio_msg("audio_file_id_456"))
    return mock_bot


# ---------------------------------------------------------------------------
# Anchor-window validation (pure function, no DB)
# ---------------------------------------------------------------------------


def test_warn_anchor_window_no_admissible_slot(caplog: pytest.LogCaptureFixture) -> None:
    """interval_hours=12 anchored at hour=1 yields slots 1,13 — both outside [6,22)? No.
    Use interval=24 anchor=3 which yields only 03:00, fully outside [06,22)."""
    with caplog.at_level(logging.WARNING, logger="cli.seed"):
        _warn_anchor_window(
            name="TestPractice",
            interval_hours=24,
            anchor_hour=3,
            send_window_start=6,
            send_window_end=22,
        )
    assert "will never fire" in caplog.text


def test_warn_anchor_window_has_admissible_slot(caplog: pytest.LogCaptureFixture) -> None:
    """interval_hours=1 anchor_hour=0 yields slots at every hour — many inside [6,22)."""
    with caplog.at_level(logging.WARNING, logger="cli.seed"):
        _warn_anchor_window(
            name="HourlyQ",
            interval_hours=1,
            anchor_hour=0,
            send_window_start=6,
            send_window_end=22,
        )
    assert "will never fire" not in caplog.text


# ---------------------------------------------------------------------------
# seed_practices
# ---------------------------------------------------------------------------


async def test_seed_practices_creates_rows(db_session: object, fake_config: object) -> None:
    """seed_practices(practices.example.yaml) creates all expected rows."""
    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory") as mock_factory,
    ):
        # Wire the mock session factory to return db_session
        mock_factory.return_value = _make_cm_factory(db_session)
        await seed_practices(PRACTICES_EXAMPLE)

    repo = PracticeRepository(db_session)
    practices = await repo.get_active_practices()
    assert len(practices) > 0

    names = {p.name for p in practices}
    assert "Morning practice" in names
    assert "Night hypnosis" in names
    assert "Hourly thought-registration question" in names


async def test_seed_practices_idempotent(db_session: object, fake_config: object) -> None:
    """Running seed_practices twice does not create duplicate rows."""
    factory = _make_cm_factory(db_session)

    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=factory),
    ):
        await seed_practices(PRACTICES_EXAMPLE)
        await seed_practices(PRACTICES_EXAMPLE)

    repo = PracticeRepository(db_session)
    practices = await repo.get_active_practices()
    names = [p.name for p in practices]
    # No duplicate names
    assert len(names) == len(set(names))


async def test_seed_practices_audio_creates_media_asset(
    db_session: object, fake_config: object
) -> None:
    """Audio practice row (Night hypnosis) gets a linked media_assets row."""
    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=_make_cm_factory(db_session)),
    ):
        await seed_practices(PRACTICES_EXAMPLE)

    repo = PracticeRepository(db_session)
    practice = await repo.get_by_name("Night hypnosis")
    assert practice is not None
    assert practice.media_asset_id is not None

    asset = await repo.get_media_asset_by_id(practice.media_asset_id)
    assert asset is not None
    assert asset.telegram_file_id == "CQACAgIAAxk..."
    assert asset.storage_path is None  # Stage 1 invariant


async def test_seed_practices_anchor_window_warning(
    db_session: object, fake_config: object, caplog: pytest.LogCaptureFixture
) -> None:
    """A misconfigured every_n_hours practice logs a WARNING during seeding."""
    import tempfile

    import yaml

    bad_practice = [
        {
            "name": "Bad cadence",
            "content_type": "text",
            "content": "test",
            "periodicity_type": "every_n_hours",
            "interval_hours": 24,
            "anchor_hour": 3,  # slot at 03:00 — outside [06, 22)
            "active": True,
            "sort_order": 1,
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(bad_practice, tmp)
        tmp_path = Path(tmp.name)

    try:
        with (
            patch("cli.seed.get_config", return_value=fake_config),
            patch("cli.seed.build_session_factory", return_value=_make_cm_factory(db_session)),
            caplog.at_level(logging.WARNING, logger="cli.seed"),
        ):
            await seed_practices(tmp_path)
        assert "will never fire" in caplog.text
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# seed_blessings
# ---------------------------------------------------------------------------


async def test_seed_blessings_creates_rows(db_session: object, fake_config: object) -> None:
    """seed_blessings creates MorningBlessing rows."""
    import tempfile

    import yaml

    blessings_data = [
        {"rotation_order": 1, "text": "Good morning 1", "active": True},
        {"rotation_order": 2, "text": "Good morning 2", "active": True},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(blessings_data, tmp)
        tmp_path = Path(tmp.name)

    try:
        with (
            patch("cli.seed.get_config", return_value=fake_config),
            patch("cli.seed.build_session_factory", return_value=_make_cm_factory(db_session)),
        ):
            await seed_blessings(tmp_path)

        repo = BlessingRepository(db_session)
        blessings = await repo.get_active_ordered()
        assert len(blessings) == 2
        assert blessings[0].text == "Good morning 1"
        assert blessings[1].text == "Good morning 2"
    finally:
        tmp_path.unlink(missing_ok=True)


async def test_seed_blessings_idempotent(db_session: object, fake_config: object) -> None:
    """Running seed_blessings twice updates rows in place without duplicates."""
    import tempfile

    import yaml

    blessings_data = [{"rotation_order": 1, "text": "Original", "active": True}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(blessings_data, tmp)
        tmp_path = Path(tmp.name)

    updated_data = [{"rotation_order": 1, "text": "Updated", "active": True}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp2:
        yaml.dump(updated_data, tmp2)
        tmp2_path = Path(tmp2.name)

    try:
        factory = _make_cm_factory(db_session)
        with (
            patch("cli.seed.get_config", return_value=fake_config),
            patch("cli.seed.build_session_factory", return_value=factory),
        ):
            await seed_blessings(tmp_path)
            await seed_blessings(tmp2_path)

        repo = BlessingRepository(db_session)
        blessings = await repo.get_active_ordered()
        assert len(blessings) == 1
        assert blessings[0].text == "Updated"
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp2_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# seed_images
# ---------------------------------------------------------------------------


async def test_seed_images_creates_media_asset_and_motivational_image(
    db_session: object, fake_config: object, tmp_path: Path
) -> None:
    """seed_images upserts a media_assets row and a motivational_images row."""
    import yaml

    img_file = tmp_path / "test.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0")  # minimal JPEG header bytes

    images_data = [{"local_path": str(img_file), "mime": "image/jpeg", "active": True}]
    yaml_file = tmp_path / "images.yaml"
    yaml_file.write_text(yaml.dump(images_data))

    mock_bot = _make_mock_bot(send_photo_file_id="TG_FILE_ID_IMG_001")

    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=_make_cm_factory(db_session)),
    ):
        await seed_images(yaml_file, bot=mock_bot)

    mock_bot.send_photo.assert_awaited_once()

    practice_repo = PracticeRepository(db_session)
    asset = await practice_repo.get_media_asset_by_telegram_file_id("TG_FILE_ID_IMG_001")
    assert asset is not None
    assert asset.kind == "image"
    assert asset.telegram_file_id == "TG_FILE_ID_IMG_001"
    assert asset.storage_path is None  # Stage 1 invariant
    assert asset.mime == "image/jpeg"

    image_repo = ImageRepository(db_session)
    motiv_img = await image_repo.get_by_media_asset_id(asset.id)
    assert motiv_img is not None
    assert motiv_img.active is True
    assert motiv_img.media_asset_id == asset.id


async def test_seed_images_idempotent(
    db_session: object, fake_config: object, tmp_path: Path
) -> None:
    """Running seed_images twice does not create duplicate media_assets or motivational_images."""
    import yaml

    img_file = tmp_path / "dup.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0")

    images_data = [{"local_path": str(img_file), "mime": "image/jpeg", "active": True}]
    yaml_file = tmp_path / "images.yaml"
    yaml_file.write_text(yaml.dump(images_data))

    mock_bot = _make_mock_bot(send_photo_file_id="TG_FILE_ID_IMG_DUP")

    factory = _make_cm_factory(db_session)
    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=factory),
    ):
        await seed_images(yaml_file, bot=mock_bot)
        await seed_images(yaml_file, bot=mock_bot)

    # Both uploads happened (two calls to send_photo)
    assert mock_bot.send_photo.await_count == 2

    # Only one media_asset row for this file_id
    from sqlalchemy import select

    result = await db_session.execute(
        select(MediaAsset).where(MediaAsset.telegram_file_id == "TG_FILE_ID_IMG_DUP")
    )
    assets = list(result.scalars().all())
    assert len(assets) == 1

    image_repo = ImageRepository(db_session)
    imgs = await image_repo.get_active()
    mi_for_asset = [i for i in imgs if i.media_asset_id == assets[0].id]
    assert len(mi_for_asset) == 1


# ---------------------------------------------------------------------------
# seed_audio
# ---------------------------------------------------------------------------


async def test_seed_audio_creates_media_asset_on_practice(
    db_session: object, fake_config: object, tmp_path: Path
) -> None:
    """seed_audio upserts a media_assets row and links it to the practice."""
    import yaml

    # First seed the practice row
    practice_repo = PracticeRepository(db_session)
    practice = Practice(
        id=uuid.uuid4(),
        user_id=123456789,
        name="Night hypnosis",
        content_type="audio",
        periodicity_type="fixed_times",
        schedule_times=["20:00"],
        anchor_hour=0,
        anchor_minute=0,
        active=True,
        sort_order=400,
    )
    await practice_repo.save(practice)
    await db_session.commit()

    audio_file = tmp_path / "hypnosis.mp3"
    audio_file.write_bytes(b"\xff\xfb")  # minimal MP3 bytes

    audio_data = [{"name": "Night hypnosis", "local_path": str(audio_file), "mime": "audio/mpeg"}]
    yaml_file = tmp_path / "audio.yaml"
    yaml_file.write_text(yaml.dump(audio_data))

    mock_bot = _make_mock_bot()
    mock_bot.send_audio = AsyncMock(return_value=_make_audio_msg("TG_FILE_ID_AUDIO_001"))

    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=_make_cm_factory(db_session)),
    ):
        await seed_audio(yaml_file, bot=mock_bot)

    mock_bot.send_audio.assert_awaited_once()

    await db_session.refresh(practice)
    assert practice.media_asset_id is not None

    asset = await practice_repo.get_media_asset_by_id(practice.media_asset_id)
    assert asset is not None
    assert asset.kind == "audio"
    assert asset.telegram_file_id == "TG_FILE_ID_AUDIO_001"
    assert asset.storage_path is None  # Stage 1 invariant
    assert asset.mime == "audio/mpeg"


async def test_seed_audio_idempotent(
    db_session: object, fake_config: object, tmp_path: Path
) -> None:
    """Running seed_audio twice updates the media_asset row rather than duplicating it."""
    import yaml

    practice_repo = PracticeRepository(db_session)
    practice = Practice(
        id=uuid.uuid4(),
        user_id=123456789,
        name="Night hypnosis",
        content_type="audio",
        periodicity_type="fixed_times",
        schedule_times=["20:00"],
        anchor_hour=0,
        anchor_minute=0,
        active=True,
        sort_order=400,
    )
    await practice_repo.save(practice)
    await db_session.commit()

    audio_file = tmp_path / "hypnosis2.mp3"
    audio_file.write_bytes(b"\xff\xfb")

    audio_data = [{"name": "Night hypnosis", "local_path": str(audio_file), "mime": "audio/mpeg"}]
    yaml_file = tmp_path / "audio.yaml"
    yaml_file.write_text(yaml.dump(audio_data))

    mock_bot = MagicMock()
    mock_bot.send_audio = AsyncMock(return_value=_make_audio_msg("TG_AUDIO_IDEM"))

    factory = _make_cm_factory(db_session)
    with (
        patch("cli.seed.get_config", return_value=fake_config),
        patch("cli.seed.build_session_factory", return_value=factory),
    ):
        await seed_audio(yaml_file, bot=mock_bot)
        await seed_audio(yaml_file, bot=mock_bot)

    assert mock_bot.send_audio.await_count == 2

    from sqlalchemy import select

    result = await db_session.execute(select(MediaAsset))
    all_assets = list(result.scalars().all())
    # Only one media_asset created across both seedings
    assert len(all_assets) == 1
    assert all_assets[0].telegram_file_id == "TG_AUDIO_IDEM"


# ---------------------------------------------------------------------------
# Context-manager factory helper
# ---------------------------------------------------------------------------


def _make_cm_factory(session: object) -> object:
    """Return a callable whose __call__ returns an async context manager yielding session."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _cm():  # type: ignore[misc]
        yield session

    def _factory():
        return _cm()

    return _factory
