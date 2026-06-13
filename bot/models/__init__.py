"""ORM model registry — import all models so Alembic autogenerate sees them."""

from bot.models.base import Base, TimestampMixin, UUIDMixin
from bot.models.user import User

__all__ = ["Base", "TimestampMixin", "UUIDMixin", "User"]
