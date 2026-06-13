"""0003 — journal: pending_prompts, journal_entries, self_assessments.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create pending_prompts, journal_entries, and self_assessments tables."""
    bind = op.get_bind()

    prompt_kind = postgresql.ENUM(
        "thought", "good_deeds", "want", "other", name="prompt_kind", create_type=False
    )
    prompt_kind.create(bind, checkfirst=True)

    entry_source = postgresql.ENUM("text", "voice", name="entry_source", create_type=False)
    entry_source.create(bind, checkfirst=True)

    assessment_set_via = postgresql.ENUM(
        "button", "clarify", name="assessment_set_via", create_type=False
    )
    assessment_set_via.create(bind, checkfirst=True)

    # --- pending_prompts ---
    op.create_table(
        "pending_prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("practice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "thought", "good_deeds", "want", "other", name="prompt_kind", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("clarify_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["practice_id"], ["practices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_prompts_user_consumed_created",
        "pending_prompts",
        ["user_id", "consumed", "created_at"],
    )

    # --- journal_entries ---
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("practice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM("text", "voice", name="entry_source", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["practice_id"], ["practices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_journal_entries_user_created",
        "journal_entries",
        ["user_id", "created_at"],
    )

    # --- self_assessments ---
    op.create_table(
        "self_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leads_to_goals", sa.Boolean(), nullable=False),
        sa.Column(
            "set_via",
            postgresql.ENUM("button", "clarify", name="assessment_set_via", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id", name="uq_self_assessment_entry"),
    )


def downgrade() -> None:
    """Drop self_assessments, journal_entries, and pending_prompts tables."""
    op.drop_table("self_assessments")
    op.drop_index("ix_journal_entries_user_created", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_pending_prompts_user_consumed_created", table_name="pending_prompts")
    op.drop_table("pending_prompts")
    op.execute("DROP TYPE IF EXISTS assessment_set_via")
    op.execute("DROP TYPE IF EXISTS entry_source")
    op.execute("DROP TYPE IF EXISTS prompt_kind")
