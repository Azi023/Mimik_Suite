"""Persist the additive Brand Kit v2 book payload on brands.

Revision ID: 3d91b84ad827
Revises: c7e90f4a1b32
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d91b84ad827"
down_revision: Union[str, None] = "c7e90f4a1b32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "brands",
        sa.Column(
            "kit",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("brands", "kit")
