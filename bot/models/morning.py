"""Morning block models: MorningBlessing, MotivationalImage, DailyAiAnalysis, ApiUsageLog."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, UUIDMixin


class MorningBlessing(Base, UUIDMixin):
    """A morning blessing text cycled in rotation_order sequence."""

    __tablename__ = "morning_blessings"
    __table_args__ = (
        UniqueConstraint("rotation_order", name="uq_morning_blessings_rotation_order"),
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    rotation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MotivationalImage(Base, UUIDMixin):
    """A motivational image backed by a MediaAsset."""

    __tablename__ = "motivational_images"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_assets.id"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    media_asset: Mapped["MediaAsset"] = relationship(  # noqa: F821
        "MediaAsset", lazy="select", foreign_keys=[media_asset_id]
    )


class DailyAiAnalysis(Base, UUIDMixin):
    """One morning AI analysis per user per calendar day."""

    __tablename__ = "daily_ai_analyses"
    __table_args__ = (
        UniqueConstraint("user_id", "analysis_date", name="uq_daily_analysis_user_date"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    n_total: Mapped[int] = mapped_column(Integer, nullable=False)
    n_leads: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApiUsageLog(Base, UUIDMixin):
    """One row per product LLM/API call for cost tracking (AC-16)."""

    __tablename__ = "api_usage_logs"
    __table_args__ = (Index("ix_api_usage_logs_created_at", "created_at"),)

    kind: Mapped[str] = mapped_column(
        Enum("analysis", "report", "transcription", name="api_usage_kind"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
