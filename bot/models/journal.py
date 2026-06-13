"""Journal models: PendingPrompt, JournalEntry, SelfAssessment."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, UUIDMixin


class PendingPrompt(Base, UUIDMixin):
    """A practice question that was sent and is awaiting a user reply.

    Durable binding anchor (Decision B1): every outgoing question writes one row;
    an incoming reply resolves the binding by reply-to message_id or falls back
    to the newest unconsumed row.  Survives process restarts (no in-memory FSM).
    """

    __tablename__ = "pending_prompts"
    __table_args__ = (
        Index("ix_pending_prompts_user_consumed_created", "user_id", "consumed", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    practice_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("practices.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(
        Enum("thought", "good_deeds", "want", "other", name="prompt_kind"),
        nullable=False,
    )
    # Telegram message_id of the outgoing bot message; used for precise reply binding
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set to True once a clarify question has been sent for this prompt's entry
    clarify_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    practice: Mapped["Practice | None"] = relationship(  # noqa: F821
        "Practice", lazy="select", foreign_keys=[practice_id]
    )


class JournalEntry(Base, UUIDMixin):
    """One user reply stored in the long-term journal.

    `text` holds the typed message or the Groq Whisper transcript; raw audio
    bytes are never persisted (AC-7).
    """

    __tablename__ = "journal_entries"
    __table_args__ = (Index("ix_journal_entries_user_created", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    practice_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("practices.id", ondelete="SET NULL"),
        nullable=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        Enum("text", "voice", name="entry_source"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    self_assessment: Mapped["SelfAssessment | None"] = relationship(
        "SelfAssessment",
        back_populates="journal_entry",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )


class SelfAssessment(Base, UUIDMixin):
    """Whether the user believes a thought leads to their goals (AC-8).

    One-to-one with JournalEntry (unique constraint on journal_entry_id).
    set_via distinguishes button press from clarify-question answer.
    """

    __tablename__ = "self_assessments"
    __table_args__ = (UniqueConstraint("journal_entry_id", name="uq_self_assessment_entry"),)

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    leads_to_goals: Mapped[bool] = mapped_column(Boolean, nullable=False)
    set_via: Mapped[str] = mapped_column(
        Enum("button", "clarify", name="assessment_set_via"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry", back_populates="self_assessment"
    )
