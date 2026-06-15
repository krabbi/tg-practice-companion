"""0009 — add 'motivational_image' to practice_content_type enum.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'motivational_image' value to practice_content_type enum."""
    op.execute("ALTER TYPE practice_content_type ADD VALUE IF NOT EXISTS 'motivational_image'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is intentionally a no-op.
    pass
