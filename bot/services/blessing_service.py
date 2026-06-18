"""Blessing rotation service (AC-3)."""

from datetime import date

from bot.models.morning import MorningBlessing
from bot.repositories.blessing_repository import BlessingRepository


class BlessingService:
    """Select the morning blessing for a given date using date-derived round-robin.

    The blessing index is derived purely from the calendar date so the rotation
    is predictable and requires no mutable cursor state:

        idx = today.toordinal() % len(active_blessings)

    Consecutive days advance through the list in rotation_order sequence and
    wrap back to the first blessing, fulfilling AC-3.  If blessings are added
    or removed the rotation adjusts automatically on the next tick — no data
    repair is needed.
    """

    def __init__(self, blessing_repo: BlessingRepository) -> None:
        self._blessing_repo = blessing_repo

    async def for_date(self, user_id: int, today: date) -> MorningBlessing | None:
        """Return the blessing for *today* for user_id.

        Returns None when there are no active blessings.  Calling this method
        multiple times with the same date always returns the same blessing.
        """
        blessings = await self._blessing_repo.get_active_ordered(user_id)
        if not blessings:
            return None
        idx = today.toordinal() % len(blessings)
        return blessings[idx]
