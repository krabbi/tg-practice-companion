"""ORM model registry — import all models so Alembic autogenerate sees them."""

from bot.models.base import Base, TimestampMixin, UUIDMixin
from bot.models.practice import MediaAsset, Practice, PracticeSend
from bot.models.user import User

__all__ = ["Base", "MediaAsset", "Practice", "PracticeSend", "TimestampMixin", "UUIDMixin", "User"]
