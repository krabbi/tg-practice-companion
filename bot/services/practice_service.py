"""Service for practice CRUD and due-now evaluation."""

from datetime import date, datetime

from bot.models.practice import Practice
from bot.repositories.practice_repository import PracticeRepository


class PracticeService:
    """Business logic for practice queries and due-now evaluation."""

    def __init__(self, practice_repo: PracticeRepository) -> None:
        self._practice_repo = practice_repo

    async def active_practices(self, user_id: int) -> list[Practice]:
        """Return all active Practice rows for user_id ordered by sort_order."""
        return await self._practice_repo.get_active_practices(user_id)

    async def due_now(self, user_id: int, local_now: datetime) -> list[Practice]:
        """Return practices that are due at the given local wall-clock time for user_id.

        Checks:
        - practice.active is True
        - start_date <= today <= end_date (if set)
        - periodicity matches local_now (fixed_times or every_n_hours phase)
        """
        practices = await self._practice_repo.get_active_practices(user_id)
        due: list[Practice] = []
        today: date = local_now.date()

        for practice in practices:
            if not self._is_in_date_range(practice, today):
                continue
            if self._is_due_at(practice, local_now):
                due.append(practice)

        return due

    @staticmethod
    def _is_in_date_range(practice: Practice, today: date) -> bool:
        """Return True if today falls within the practice's optional date range."""
        if practice.start_date is not None and today < practice.start_date.date():
            return False
        return not (practice.end_date is not None and today > practice.end_date.date())

    @staticmethod
    def _is_due_at(practice: Practice, local_now: datetime) -> bool:
        """Return True if the practice fires at local_now.

        fixed_times: fires when local_now's HH:MM is in schedule_times.
        every_n_hours: fires when:
          - local_now.minute == anchor_minute (default 0)
          - local_now.hour % interval_hours == anchor_hour % interval_hours
        """
        if practice.periodicity_type == "fixed_times":
            if not practice.schedule_times:
                return False
            current_hhmm = local_now.strftime("%H:%M")
            return current_hhmm in practice.schedule_times

        if practice.periodicity_type == "every_n_hours":
            interval = practice.interval_hours
            if not interval or interval <= 0:
                return False
            anchor_h = practice.anchor_hour if practice.anchor_hour is not None else 0
            anchor_m = practice.anchor_minute if practice.anchor_minute is not None else 0
            # Minute must match the anchor minute
            if local_now.minute != anchor_m:
                return False
            # Hour phase: due when hour ≡ anchor_hour (mod interval_hours)
            return local_now.hour % interval == anchor_h % interval

        return False
