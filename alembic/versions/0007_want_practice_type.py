"""0007 — add 'want' to practice_content_type enum.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'want' value to practice_content_type enum."""
    # ADD VALUE is transactional in PostgreSQL 12+; IF NOT EXISTS makes it idempotent.
    op.execute("ALTER TYPE practice_content_type ADD VALUE IF NOT EXISTS 'want'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is intentionally a no-op.
    pass
