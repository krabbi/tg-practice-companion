"""Integration tests for morning-block repositories using aiosqlite :memory: DB.

Covers:
- BlessingRepository: save, get_by_id, get_active_ordered, duplicate rotation_order raises
- ImageRepository: save, get_by_id, get_active, inactive excluded
- AnalysisRepository: save, get_by_id, get_by_user_and_date, duplicate (user_id, date) raises
- ApiUsageRepository: save, get_by_id, sum_cost_since
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.morning import ApiUsageLog, DailyAiAnalysis, MorningBlessing, MotivationalImage
from bot.models.practice import MediaAsset
from bot.repositories.analysis_repository import AnalysisRepository
from bot.repositories.api_usage_repository import ApiUsageRepository
from bot.repositories.blessing_repository import BlessingRepository
from bot.repositories.image_repository import ImageRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


TEST_USER_ID = 123456789


def make_blessing(text: str = "Blessed morning", rotation_order: int = 1) -> MorningBlessing:
    b = MorningBlessing()
    b.id = uuid.uuid4()
    b.text = text
    b.rotation_order = rotation_order
    b.active = True
    b.user_id = TEST_USER_ID
    return b


def make_media_asset() -> MediaAsset:
    a = MediaAsset()
    a.id = uuid.uuid4()
    a.kind = "image"
    a.telegram_file_id = "AgACAgI_image123"
    a.storage_path = None
    a.mime = "image/jpeg"
    a.user_id = TEST_USER_ID
    return a


def make_image(media_asset_id: uuid.UUID, active: bool = True) -> MotivationalImage:
    img = MotivationalImage()
    img.id = uuid.uuid4()
    img.media_asset_id = media_asset_id
    img.active = active
    img.user_id = TEST_USER_ID
    return img


def make_analysis(
    user_id: int = 123456,
    analysis_date: date = date(2026, 6, 13),
    n_total: int = 5,
    n_leads: int = 3,
    message: str = "Good progress!",
) -> DailyAiAnalysis:
    a = DailyAiAnalysis()
    a.id = uuid.uuid4()
    a.user_id = user_id
    a.analysis_date = analysis_date
    a.n_total = n_total
    a.n_leads = n_leads
    a.message = message
    return a


def make_usage_log(
    kind: str = "analysis",
    model: str = "claude-haiku-4-5-20251001",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: Decimal = Decimal("0.000150"),
    audio_seconds: float | None = None,
    created_at: datetime | None = None,
) -> ApiUsageLog:
    log = ApiUsageLog()
    log.id = uuid.uuid4()
    log.kind = kind
    log.model = model
    log.input_tokens = input_tokens
    log.output_tokens = output_tokens
    log.cost_usd = cost_usd
    log.audio_seconds = audio_seconds
    if created_at is not None:
        log.created_at = created_at
    return log


# ---------------------------------------------------------------------------
# BlessingRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blessing_save_and_get_by_id(db_session: AsyncSession) -> None:
    """save flushes and refreshes; get_by_id returns the same row."""
    repo = BlessingRepository(db_session)

    b = make_blessing(text="Morning light", rotation_order=1)
    saved = await repo.save(b)

    assert saved.id is not None
    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.text == "Morning light"
    assert found.rotation_order == 1


@pytest.mark.asyncio
async def test_blessing_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that does not exist."""
    repo = BlessingRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_blessing_get_active_ordered(db_session: AsyncSession) -> None:
    """get_active_ordered returns only active blessings, sorted by rotation_order."""
    repo = BlessingRepository(db_session)

    b1 = make_blessing(text="third", rotation_order=3)
    b2 = make_blessing(text="first", rotation_order=1)
    b3 = make_blessing(text="second", rotation_order=2)
    b3.active = False
    for b in (b1, b2, b3):
        db_session.add(b)
    await db_session.flush()

    result = await repo.get_active_ordered(TEST_USER_ID)

    assert len(result) == 2
    assert result[0].text == "first"
    assert result[1].text == "third"


@pytest.mark.asyncio
async def test_blessing_get_active_ordered_empty(db_session: AsyncSession) -> None:
    """get_active_ordered returns empty list when no active blessings exist."""
    repo = BlessingRepository(db_session)
    result = await repo.get_active_ordered(TEST_USER_ID)
    assert result == []


@pytest.mark.asyncio
async def test_blessing_duplicate_rotation_order_raises(db_session: AsyncSession) -> None:
    """Inserting two blessings with the same rotation_order raises IntegrityError."""
    repo = BlessingRepository(db_session)

    b1 = make_blessing(rotation_order=1)
    await repo.save(b1)

    b2 = make_blessing(rotation_order=1)
    with pytest.raises(IntegrityError):
        await repo.save(b2)


# ---------------------------------------------------------------------------
# ImageRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_save_and_get_by_id(db_session: AsyncSession) -> None:
    """save flushes and refreshes; get_by_id returns the same row."""
    asset = make_media_asset()
    db_session.add(asset)
    await db_session.flush()

    repo = ImageRepository(db_session)
    img = make_image(media_asset_id=asset.id)
    saved = await repo.save(img)

    assert saved.id is not None
    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.media_asset_id == asset.id


@pytest.mark.asyncio
async def test_image_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that does not exist."""
    repo = ImageRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_image_get_active_excludes_inactive(db_session: AsyncSession) -> None:
    """get_active returns only images with active=True."""
    asset = make_media_asset()
    db_session.add(asset)
    await db_session.flush()

    repo = ImageRepository(db_session)
    active_img = make_image(media_asset_id=asset.id, active=True)
    inactive_img = make_image(media_asset_id=asset.id, active=False)
    db_session.add(active_img)
    db_session.add(inactive_img)
    await db_session.flush()

    result = await repo.get_active(TEST_USER_ID)

    assert len(result) == 1
    assert result[0].id == active_img.id


@pytest.mark.asyncio
async def test_image_get_active_empty(db_session: AsyncSession) -> None:
    """get_active returns empty list when no active images exist."""
    repo = ImageRepository(db_session)
    result = await repo.get_active(TEST_USER_ID)
    assert result == []


# ---------------------------------------------------------------------------
# AnalysisRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_save_and_get_by_id(db_session: AsyncSession) -> None:
    """save flushes and refreshes; get_by_id returns the correct row."""
    repo = AnalysisRepository(db_session)

    a = make_analysis(user_id=111, n_total=10, n_leads=7, message="Well done")
    saved = await repo.save(a)

    assert saved.id is not None
    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.user_id == 111
    assert found.n_total == 10
    assert found.n_leads == 7
    assert found.message == "Well done"


@pytest.mark.asyncio
async def test_analysis_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that does not exist."""
    repo = AnalysisRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_analysis_get_by_user_and_date(db_session: AsyncSession) -> None:
    """get_by_user_and_date returns the matching row."""
    repo = AnalysisRepository(db_session)

    a = make_analysis(user_id=222, analysis_date=date(2026, 6, 13))
    await repo.save(a)

    found = await repo.get_by_user_and_date(222, date(2026, 6, 13))
    assert found is not None
    assert found.user_id == 222
    assert found.analysis_date == date(2026, 6, 13)


@pytest.mark.asyncio
async def test_analysis_get_by_user_and_date_returns_none_for_miss(
    db_session: AsyncSession,
) -> None:
    """get_by_user_and_date returns None when no row matches."""
    repo = AnalysisRepository(db_session)
    result = await repo.get_by_user_and_date(999, date(2026, 1, 1))
    assert result is None


@pytest.mark.asyncio
async def test_analysis_duplicate_user_date_raises(db_session: AsyncSession) -> None:
    """Inserting two analyses for the same (user_id, analysis_date) raises IntegrityError."""
    repo = AnalysisRepository(db_session)

    a1 = make_analysis(user_id=333, analysis_date=date(2026, 6, 13))
    await repo.save(a1)

    a2 = make_analysis(user_id=333, analysis_date=date(2026, 6, 13))
    with pytest.raises(IntegrityError):
        await repo.save(a2)


# ---------------------------------------------------------------------------
# ApiUsageRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_usage_save_and_get_by_id(db_session: AsyncSession) -> None:
    """save flushes and refreshes; get_by_id returns the correct row."""
    repo = ApiUsageRepository(db_session)

    log = make_usage_log(
        kind="transcription",
        model="whisper-large-v3-turbo",
        input_tokens=0,
        output_tokens=0,
        audio_seconds=12.5,
        cost_usd=Decimal("0.001250"),
    )
    saved = await repo.save(log)

    assert saved.id is not None
    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.kind == "transcription"
    assert found.audio_seconds == pytest.approx(12.5)
    assert float(found.cost_usd) == pytest.approx(0.001250)


@pytest.mark.asyncio
async def test_api_usage_get_by_id_returns_none_for_unknown(db_session: AsyncSession) -> None:
    """get_by_id returns None for a UUID that does not exist."""
    repo = ApiUsageRepository(db_session)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_api_usage_sum_cost_since_includes_matching_rows(db_session: AsyncSession) -> None:
    """sum_cost_since sums cost_usd for rows at or after the cutoff."""
    repo = ApiUsageRepository(db_session)

    cutoff = datetime(2026, 6, 13, 6, 0, 0, tzinfo=UTC)
    before = datetime(2026, 6, 13, 5, 0, 0, tzinfo=UTC)
    after = datetime(2026, 6, 13, 7, 0, 0, tzinfo=UTC)

    log_before = make_usage_log(cost_usd=Decimal("0.010000"), created_at=before)
    log_after1 = make_usage_log(cost_usd=Decimal("0.020000"), created_at=after)
    log_at_cutoff = make_usage_log(cost_usd=Decimal("0.005000"), created_at=cutoff)

    for log in (log_before, log_after1, log_at_cutoff):
        db_session.add(log)
    await db_session.flush()

    total = await repo.sum_cost_since(cutoff)
    assert float(total) == pytest.approx(0.025000)


@pytest.mark.asyncio
async def test_api_usage_sum_cost_since_returns_zero_when_empty(db_session: AsyncSession) -> None:
    """sum_cost_since returns Decimal('0') when no rows match."""
    repo = ApiUsageRepository(db_session)
    future = datetime(2099, 1, 1, tzinfo=UTC)
    total = await repo.sum_cost_since(future)
    assert total == Decimal("0")


@pytest.mark.asyncio
async def test_api_usage_all_kinds_accepted(db_session: AsyncSession) -> None:
    """All three kind values (analysis, report, transcription) are accepted."""
    repo = ApiUsageRepository(db_session)

    for kind in ("analysis", "report", "transcription"):
        log = make_usage_log(kind=kind)
        log.id = uuid.uuid4()
        saved = await repo.save(log)
        assert saved.kind == kind
