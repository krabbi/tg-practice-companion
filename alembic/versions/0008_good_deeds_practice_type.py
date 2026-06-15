"""0008 — add 'good_deeds' to practice_content_type enum.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'good_deeds' value to practice_content_type enum."""
    op.execute("ALTER TYPE practice_content_type ADD VALUE IF NOT EXISTS 'good_deeds'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is intentionally a no-op.
    pass
