"""0005 — add last_blessing_date to users for morning blessing daily dedup.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add last_blessing_date to users (daily dedup for morning blessing)."""
    op.add_column("users", sa.Column("last_blessing_date", sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove last_blessing_date from users."""
    op.drop_column("users", "last_blessing_date")
