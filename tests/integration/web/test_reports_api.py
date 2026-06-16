"""Integration tests for web/routers/reports.py — period report API."""

from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Config
from bot.models.base import Base
from bot.models.journal import JournalEntry, SelfAssessment
from bot.models.lists import GoodDeed
from bot.models.practice import Practice, PracticeSend
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


@pytest.fixture
async def engine_and_factory():
    """Shared in-memory SQLite engine with schema created once per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(engine_and_factory):
    """AsyncClient with isolated in-memory SQLite DB and get_db_session overridden."""
    engine, factory = engine_and_factory

    async def _override_session():
        async with factory() as session:
            yield session

    config = Config.model_validate(_BASE_CONFIG)
    app = create_app(config)
    app.dependency_overrides[get_db_session] = _override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict:
    """Bearer JWT headers for the allowlisted test user."""
    config = Config.model_validate(_BASE_CONFIG)
    token = create_jwt({"id": ALLOWED_USER_ID}, config.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded(engine_and_factory):
    """Seed journal entries, self-assessments, good deeds, and practice sends."""
    _, factory = engine_and_factory
    async with factory() as session:
        practice = Practice(
            name="Morning Question",
            content_type="question",
            content="How do you feel?",
            periodicity_type="fixed_times",
            schedule_times=["09:00"],
        )
        session.add(practice)
        await session.flush()

        # 3 journal entries in June 2026
        entries = [
            JournalEntry(
                user_id=ALLOWED_USER_ID,
                practice_id=practice.id,
                text=f"Entry {i}",
                source="text",
                created_at=datetime(2026, 6, i, 9, 0, tzinfo=UTC),
            )
            for i in range(1, 4)
        ]
        session.add_all(entries)
        await session.flush()

        # 2 self-assessments: both lead to goals
        sa1 = SelfAssessment(
            journal_entry_id=entries[0].id,
            leads_to_goals=True,
            set_via="button",
        )
        sa2 = SelfAssessment(
            journal_entry_id=entries[1].id,
            leads_to_goals=False,
            set_via="clarify",
        )
        session.add_all([sa1, sa2])

        # 2 good deeds in June 2026
        deeds = [
            GoodDeed(
                user_id=ALLOWED_USER_ID,
                text=f"Good deed {i}",
                deed_date=date(2026, 6, i),
            )
            for i in range(1, 3)
        ]
        session.add_all(deeds)

        # 4 practice sends in June 2026
        sends = [
            PracticeSend(
                practice_id=practice.id,
                user_id=ALLOWED_USER_ID,
                slot_key=f"2026-06-0{i}T09:00",
                sent_at=datetime(2026, 6, i, 9, 0, tzinfo=UTC),
            )
            for i in range(1, 5)
        ]
        session.add_all(sends)
        await session.commit()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


async def test_report_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/reports with no token returns 401."""
    resp = await client.get("/api/reports?date_from=2026-06-01&date_to=2026-06-30")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Period report content
# ---------------------------------------------------------------------------


async def test_report_empty_period(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/reports for a period with no data returns zeros."""
    resp = await client.get(
        "/api/reports?date_from=2025-01-01&date_to=2025-01-31", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_total"] == 0
    assert body["n_leads"] == 0
    assert body["n_practices"] == 0
    assert body["n_good_deeds"] == 0


async def test_report_correct_totals(client: AsyncClient, auth_headers: dict, seeded) -> None:
    """GET /api/reports returns correct n_total, n_leads, n_practices, n_good_deeds."""
    resp = await client.get(
        "/api/reports?date_from=2026-06-01&date_to=2026-06-30", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_from"] == "2026-06-01"
    assert body["date_to"] == "2026-06-30"
    assert body["n_total"] == 3
    assert body["n_leads"] == 1
    assert body["n_practices"] == 4
    assert body["n_good_deeds"] == 2


async def test_report_date_range_respected(client: AsyncClient, auth_headers: dict, seeded) -> None:
    """GET /api/reports for a sub-range returns only data in that range."""
    resp = await client.get(
        "/api/reports?date_from=2026-06-01&date_to=2026-06-01", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_total"] == 1
    assert body["n_leads"] == 1
    assert body["n_good_deeds"] == 1


async def test_report_missing_params_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/reports without required query params returns 422."""
    resp = await client.get("/api/reports", headers=auth_headers)
    assert resp.status_code == 422
