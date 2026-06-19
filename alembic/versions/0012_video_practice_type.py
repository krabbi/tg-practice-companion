"""0012 — add 'video' to practice_content_type and media_asset_kind enums.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'video' value to practice_content_type and media_asset_kind enums."""
    op.execute("ALTER TYPE practice_content_type ADD VALUE IF NOT EXISTS 'video'")
    op.execute("ALTER TYPE media_asset_kind ADD VALUE IF NOT EXISTS 'video'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is intentionally a no-op.
    pass
