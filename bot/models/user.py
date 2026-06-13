"""User model — one row per whitelisted Telegram user."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Represents the single whitelisted Telegram user and their preferences."""

    __tablename__ = "users"

    # Telegram user ID is the natural primary key (BigInteger to match Telegram spec)
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # IANA timezone string, e.g. "Europe/Minsk"; nullable until first-run setup (M5)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # UI language; "ru" by default
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")

    # When set, no practices are sent until this date (AC-18 skip-day, M1)
    skip_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # UTC instant of the last timezone change; consumed by the backward-jump guard (M1/M5)
    tz_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
