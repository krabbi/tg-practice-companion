"""Practice engine models: MediaAsset, Practice, PracticeSend."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin, UUIDMixin


class MediaAsset(Base, UUIDMixin, TimestampMixin):
    """Owned media entity for audio/image practices.

    Stage 1: telegram_file_id is populated; storage_path stays null.
    Stage 2 (TMA upload): storage_path is written by the admin upload flow.
    Invariant: at least one of storage_path / telegram_file_id must be non-null
    (enforced at the service layer).
    """

    __tablename__ = "media_assets"

    kind: Mapped[str] = mapped_column(
        Enum("audio", "image", name="media_asset_kind"),
        nullable=False,
    )
    # Object-store/filesystem path for original bytes; null in Stage 1
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Telegram file ID used for re-sending without re-uploading (AC-2)
    telegram_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Practice(Base, UUIDMixin, TimestampMixin):
    """A single schedulable practice definition.

    Content type determines which columns are relevant:
    - question / text: content holds the body
    - audio / image: media_asset_id points to a MediaAsset row
    """

    __tablename__ = "practices"
    __table_args__ = (Index("ix_practices_active", "active"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    content_type: Mapped[str] = mapped_column(
        Enum("question", "text", "audio", "image", name="practice_content_type"),
        nullable=False,
    )
    # Body for question/text practices; null for audio/image
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FK to MediaAsset for audio/image practices
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_assets.id"),
        nullable=True,
    )

    periodicity_type: Mapped[str] = mapped_column(
        Enum("every_n_hours", "fixed_times", name="practice_periodicity_type"),
        nullable=False,
    )
    # Used when periodicity_type == "every_n_hours"
    interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Used when periodicity_type == "fixed_times"; list of "HH:MM" strings
    schedule_times: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Phase anchor against local midnight; cadence is anchored here, never to window start
    anchor_hour: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    anchor_minute: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional date range for the practice to be active
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    media_asset: Mapped["MediaAsset | None"] = relationship(
        "MediaAsset", lazy="select", foreign_keys=[media_asset_id]
    )


class PracticeSend(Base, UUIDMixin):
    """Dedup ledger: one row per (practice, slot) pair that has been sent.

    The unique index on (practice_id, slot_key) is the idempotency guard —
    a second tick that would send the same slot fails the INSERT and is skipped.
    """

    __tablename__ = "practice_sends"
    __table_args__ = (UniqueConstraint("practice_id", "slot_key", name="uq_practice_send"),)

    practice_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("practices.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # "YYYY-MM-DDTHH:MM" local wall-time string, e.g. "2026-06-10T13:00"
    slot_key: Mapped[str] = mapped_column(String(40), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
