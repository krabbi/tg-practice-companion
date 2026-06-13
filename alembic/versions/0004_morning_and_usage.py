"""0004 — morning block and API usage logging: morning_blessings, motivational_images,
daily_ai_analyses, api_usage_logs.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create morning_blessings, motivational_images, daily_ai_analyses, api_usage_logs."""
    bind = op.get_bind()

    api_usage_kind = postgresql.ENUM(
        "analysis", "report", "transcription", name="api_usage_kind", create_type=False
    )
    api_usage_kind.create(bind, checkfirst=True)

    # --- morning_blessings ---
    op.create_table(
        "morning_blessings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("rotation_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rotation_order", name="uq_morning_blessings_rotation_order"),
    )

    # --- motivational_images ---
    op.create_table(
        "motivational_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- daily_ai_analyses ---
    op.create_table(
        "daily_ai_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("n_total", sa.Integer(), nullable=False),
        sa.Column("n_leads", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "analysis_date", name="uq_daily_analysis_user_date"),
    )

    # --- api_usage_logs ---
    op.create_table(
        "api_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "analysis", "report", "transcription", name="api_usage_kind", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("audio_seconds", sa.Float(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_usage_logs_created_at",
        "api_usage_logs",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop api_usage_logs, daily_ai_analyses, motivational_images, morning_blessings."""
    op.drop_index("ix_api_usage_logs_created_at", table_name="api_usage_logs")
    op.drop_table("api_usage_logs")
    op.drop_table("daily_ai_analyses")
    op.drop_table("motivational_images")
    op.drop_table("morning_blessings")
    op.execute("DROP TYPE IF EXISTS api_usage_kind")
