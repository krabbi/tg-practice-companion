"""0010 — add user_id to practices, media_assets, morning_blessings, motivational_images, api_usage_logs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-18 00:00:00.000000

All column additions and constraint changes use op.batch_alter_table so that the migration
works on both SQLite (used by unit tests, which cannot ALTER NOT NULL or swap UNIQUE in place)
and Postgres (CI integration tests and production).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that get NOT NULL FK user_id → users.telegram_id
_FK_TABLES = ("practices", "media_assets", "morning_blessings", "motivational_images")

# api_usage_logs gets a nullable user_id (attribution only)
_NULLABLE_TABLE = "api_usage_logs"


def upgrade() -> None:
    """Add user_id to content/config tables; backfill from the single existing user."""
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: add nullable user_id to all five tables
    # ------------------------------------------------------------------
    for table in (*_FK_TABLES, _NULLABLE_TABLE):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.BigInteger(), nullable=True))

    # ------------------------------------------------------------------
    # Step 2: backfill — fill user_id from MIN(telegram_id) in users
    # ------------------------------------------------------------------
    result = bind.execute(sa.text("SELECT MIN(telegram_id) FROM users"))
    min_user_id = result.scalar()

    if min_user_id is None:
        # users table is empty: guard against half-migrated non-empty content tables
        for table in _FK_TABLES:
            count_row = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}"))
            if (count_row.scalar() or 0) > 0:
                raise RuntimeError(
                    f"Table '{table}' has rows but 'users' is empty — cannot backfill "
                    "user_id. Populate the users table first, then re-run the migration."
                )
        # If all FK tables are empty, nothing to backfill; api_usage_logs stays nullable.
    else:
        for table in (*_FK_TABLES, _NULLABLE_TABLE):
            bind.execute(
                sa.text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL").bindparams(
                    uid=min_user_id
                )
            )

    # ------------------------------------------------------------------
    # Step 3a: practices — NOT NULL + FK + swap index
    # ------------------------------------------------------------------
    with op.batch_alter_table("practices", recreate="always") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.create_foreign_key("fk_practices_user_id", "users", ["user_id"], ["telegram_id"])
        # Replace the single-column active index with a composite (user_id, active) index
        batch_op.drop_index("ix_practices_active")
        batch_op.create_index("ix_practices_user_active", ["user_id", "active"])

    # ------------------------------------------------------------------
    # Step 3b: media_assets — NOT NULL + FK + user_id index
    # ------------------------------------------------------------------
    with op.batch_alter_table("media_assets", recreate="always") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.create_foreign_key(
            "fk_media_assets_user_id", "users", ["user_id"], ["telegram_id"]
        )
        batch_op.create_index("ix_media_assets_user_id", ["user_id"])

    # ------------------------------------------------------------------
    # Step 3c: morning_blessings — NOT NULL + FK + composite unique + user_id index
    # ------------------------------------------------------------------
    with op.batch_alter_table("morning_blessings", recreate="always") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.create_foreign_key(
            "fk_morning_blessings_user_id", "users", ["user_id"], ["telegram_id"]
        )
        # Swap global unique(rotation_order) → composite unique(user_id, rotation_order)
        batch_op.drop_constraint("uq_morning_blessings_rotation_order", type_="unique")
        batch_op.create_unique_constraint(
            "uq_morning_blessings_user_rotation", ["user_id", "rotation_order"]
        )
        batch_op.create_index("ix_morning_blessings_user_id", ["user_id"])

    # ------------------------------------------------------------------
    # Step 3d: motivational_images — NOT NULL + FK + user_id index
    # ------------------------------------------------------------------
    with op.batch_alter_table("motivational_images", recreate="always") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.create_foreign_key(
            "fk_motivational_images_user_id", "users", ["user_id"], ["telegram_id"]
        )
        batch_op.create_index("ix_motivational_images_user_id", ["user_id"])

    # ------------------------------------------------------------------
    # Step 3e: api_usage_logs — stays nullable, just add user_id index
    # ------------------------------------------------------------------
    with op.batch_alter_table("api_usage_logs") as batch_op:
        batch_op.create_index("ix_api_usage_logs_user_id", ["user_id"])


def downgrade() -> None:
    """Drop user_id columns and restore the global uq_morning_blessings_rotation_order.

    WARNING: downgrade is unsafe once 2+ users share a rotation_order value — rows from
    the second user would violate the restored global uniqueness constraint.
    """
    # api_usage_logs — drop index and user_id column
    with op.batch_alter_table("api_usage_logs") as batch_op:
        batch_op.drop_index("ix_api_usage_logs_user_id")
        batch_op.drop_column("user_id")

    # motivational_images — drop index, FK, and user_id column
    with op.batch_alter_table("motivational_images", recreate="always") as batch_op:
        batch_op.drop_index("ix_motivational_images_user_id")
        batch_op.drop_constraint("fk_motivational_images_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    # morning_blessings — restore global unique, drop composite unique, FK, index, and column
    with op.batch_alter_table("morning_blessings", recreate="always") as batch_op:
        batch_op.drop_index("ix_morning_blessings_user_id")
        batch_op.drop_constraint("fk_morning_blessings_user_id", type_="foreignkey")
        batch_op.drop_constraint("uq_morning_blessings_user_rotation", type_="unique")
        batch_op.create_unique_constraint("uq_morning_blessings_rotation_order", ["rotation_order"])
        batch_op.drop_column("user_id")

    # media_assets — drop index, FK, and user_id column; restore ix_practices_active
    with op.batch_alter_table("media_assets", recreate="always") as batch_op:
        batch_op.drop_index("ix_media_assets_user_id")
        batch_op.drop_constraint("fk_media_assets_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    # practices — swap composite index back to single-column, drop FK and user_id column
    with op.batch_alter_table("practices", recreate="always") as batch_op:
        batch_op.drop_index("ix_practices_user_active")
        batch_op.create_index("ix_practices_active", ["active"])
        batch_op.drop_constraint("fk_practices_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
