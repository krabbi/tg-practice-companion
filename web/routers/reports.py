"""Period-report read API — Stage 2 web admin (AC-21)."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.practice_send_repository import PracticeSendRepository
from bot.services.report_service import ReportService
from web.dependencies import get_current_user, get_db_session

router = APIRouter(prefix="/api/reports", tags=["reports"])


class PeriodReportResponse(BaseModel):
    """Aggregated statistics for a date range."""

    date_from: date
    date_to: date
    n_total: int
    n_leads: int
    n_practices: int
    n_good_deeds: int


def _make_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ReportService:
    return ReportService(
        JournalRepository(session),
        GoodDeedRepository(session),
        PracticeSendRepository(session),
    )


@router.get("", response_model=PeriodReportResponse)
async def get_period_report(
    date_from: date,
    date_to: date,
    service: ReportService = Depends(_make_service),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
) -> PeriodReportResponse:
    """Return aggregated statistics for the authenticated user over [date_from, date_to].

    Includes self-assessment dynamics (n_leads/n_total), practice send count,
    and good deeds count. Text/JSON only — no charts.
    """
    user_id: int = current_user["id"]
    result = await service.build(user_id, date_from, date_to)
    return PeriodReportResponse(
        date_from=date_from,
        date_to=date_to,
        n_total=result.n_total,
        n_leads=result.n_leads,
        n_practices=result.n_practices,
        n_good_deeds=result.n_good_deeds,
    )
