"""0006 — M4 lists: want_list_items and good_deeds tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create want_list_items and good_deeds tables."""
    op.create_table(
        "want_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "good_deeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("deed_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_good_deeds_user_id_deed_date", "good_deeds", ["user_id", "deed_date"])


def downgrade() -> None:
    """Drop want_list_items and good_deeds tables."""
    op.drop_index("ix_good_deeds_user_id_deed_date", table_name="good_deeds")
    op.drop_table("good_deeds")
    op.drop_table("want_list_items")
