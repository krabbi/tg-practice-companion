"""ORM model registry — import all models so Alembic autogenerate sees them."""

from bot.models.base import Base, TimestampMixin, UUIDMixin
from bot.models.journal import JournalEntry, PendingPrompt, SelfAssessment
from bot.models.lists import GoodDeed, WantListItem
from bot.models.morning import ApiUsageLog, DailyAiAnalysis, MorningBlessing, MotivationalImage
from bot.models.practice import MediaAsset, Practice, PracticeSend
from bot.models.user import User

__all__ = [
    "ApiUsageLog",
    "Base",
    "DailyAiAnalysis",
    "GoodDeed",
    "JournalEntry",
    "MediaAsset",
    "MorningBlessing",
    "MotivationalImage",
    "PendingPrompt",
    "Practice",
    "PracticeSend",
    "SelfAssessment",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "WantListItem",
]
