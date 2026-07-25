"""Add audited job soft-delete/update and tenant suspension state.

Revision ID: d41f83a2c906
Revises: 7a6f2d1c9b04
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d41f83a2c906"
down_revision: Union[str, None] = "7a6f2d1c9b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("jobs", sa.Column("updated_by", sa.JSON(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("jobs", sa.Column("deleted_by", sa.JSON(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("suspension_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("suspension_changed_by", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "suspension_changed_by")
    op.drop_column("tenants", "suspension_changed_at")
    op.drop_column("tenants", "suspended_at")
    op.drop_column("jobs", "deleted_by")
    op.drop_column("jobs", "deleted_at")
    op.drop_column("jobs", "updated_by")
    op.drop_column("jobs", "updated_at")
