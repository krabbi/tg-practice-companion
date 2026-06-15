"""Period report service (AC-12, M5).

Builds a deterministic plain-text report aggregating journal entries,
self-assessment dynamics, practice-send counts, and good deeds over a date range.
No LLM is used in this flow — the report is purely data-driven.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.repositories.good_deed_repository import GoodDeedRepository
from bot.repositories.journal_repository import JournalRepository
from bot.repositories.practice_send_repository import PracticeSendRepository


@dataclass(frozen=True)
class ReportResult:
    """Result returned by ReportService.build."""

    text: str
    n_total: int
    n_leads: int
    n_practices: int
    n_good_deeds: int


class ReportService:
    """Aggregate statistics for a date range and render a plain-text report (AC-12).

    The report is fully deterministic — no LLM is involved.
    """

    def __init__(
        self,
        session: AsyncSession,
        journal_repo: JournalRepository,
        good_deed_repo: GoodDeedRepository,
        send_repo: PracticeSendRepository,
    ) -> None:
        self._session = session
        self._journal_repo = journal_repo
        self._good_deed_repo = good_deed_repo
        self._send_repo = send_repo

    async def build(
        self,
        user_id: int,
        start: date,
        end: date,
        lang: str = "ru",
    ) -> ReportResult:
        """Aggregate data for user_id over [start, end] and return a plain-text report.

        The report includes:
        - Total journal entries and how many lead to goals (self-assessment dynamics).
        - Number of practices sent in the period (from practice_sends).
        - List of good deeds recorded in the period.
        """
        # Journal stats
        stats = await self._journal_repo.period_stats(user_id, start, end)
        n_total = stats.n_total
        n_leads = stats.n_leads

        # Practice sends count
        n_practices = await self._send_repo.count_in_period(user_id, start, end)

        # Good deeds list
        deeds = await self._good_deed_repo.list_by_date_range(user_id, start, end)
        n_good_deeds = len(deeds)

        # Build plain-text report
        lines: list[str] = []
        lines.append(t("report_header", lang).format(start=start.isoformat(), end=end.isoformat()))
        lines.append("")

        if n_total == 0 and n_practices == 0 and n_good_deeds == 0:
            lines.append(t("report_no_data", lang))
        else:
            if n_total > 0 or n_practices > 0:
                lines.append(t("report_total_entries", lang).format(n=n_total))
                if n_total > 0:
                    lines.append(
                        t("report_leads_fraction", lang).format(leads=n_leads, total=n_total)
                    )
                lines.append(t("report_practices_header", lang).format(n=n_practices))
                lines.append("")

            lines.append(t("report_good_deeds_header", lang))
            if n_good_deeds == 0:
                lines.append(t("report_good_deeds_empty", lang))
            else:
                for deed in deeds:
                    lines.append(f"• [{deed.deed_date.isoformat()}] {deed.text}")

        return ReportResult(
            text="\n".join(lines),
            n_total=n_total,
            n_leads=n_leads,
            n_practices=n_practices,
            n_good_deeds=n_good_deeds,
        )
