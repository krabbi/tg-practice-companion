"""0011 — add original_filename to media_assets.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-19 00:00:00.000000

Adds a nullable String(255) column `original_filename` to `media_assets`.
The column holds the original browser-provided filename at upload time.
Uses batch_alter_table so the migration works on both SQLite (unit tests)
and Postgres (CI integration tests and production).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add original_filename column to media_assets."""
    with op.batch_alter_table("media_assets") as batch_op:
        batch_op.add_column(sa.Column("original_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    """Drop original_filename column from media_assets."""
    with op.batch_alter_table("media_assets") as batch_op:
        batch_op.drop_column("original_filename")
