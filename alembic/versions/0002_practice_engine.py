"""0002 — practice engine: media_assets, practices, practice_sends.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create media_assets, practices, and practice_sends tables."""
    # --- media_assets ---
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("audio", "image", name="media_asset_kind"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=256), nullable=True),
        sa.Column("mime", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- practices ---
    op.create_table(
        "practices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum("question", "text", "audio", "image", name="practice_content_type"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "periodicity_type",
            sa.Enum("every_n_hours", "fixed_times", name="practice_periodicity_type"),
            nullable=False,
        ),
        sa.Column("interval_hours", sa.Integer(), nullable=True),
        sa.Column("schedule_times", sa.JSON(), nullable=True),
        sa.Column("anchor_hour", sa.Integer(), nullable=True),
        sa.Column("anchor_minute", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("start_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practices_active", "practices", ["active"])

    # --- practice_sends ---
    op.create_table(
        "practice_sends",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("practice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("slot_key", sa.String(length=40), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["practice_id"], ["practices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("practice_id", "slot_key", name="uq_practice_send"),
    )


def downgrade() -> None:
    """Drop practice_sends, practices, and media_assets tables."""
    op.drop_table("practice_sends")
    op.drop_index("ix_practices_active", table_name="practices")
    op.drop_table("practices")
    op.drop_table("media_assets")
    op.execute("DROP TYPE IF EXISTS practice_periodicity_type")
    op.execute("DROP TYPE IF EXISTS practice_content_type")
    op.execute("DROP TYPE IF EXISTS media_asset_kind")
