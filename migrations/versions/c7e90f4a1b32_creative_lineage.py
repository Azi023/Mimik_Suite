"""creative_lineage

Revision ID: c7e90f4a1b32
Revises: 27bc3b786ef3
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e90f4a1b32"
down_revision: Union[str, None] = "27bc3b786ef3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "creative_docs",
        sa.Column("parent_id", sa.String(), nullable=True),
    )
    op.add_column(
        "creative_docs",
        sa.Column("created_by", sa.JSON(), nullable=True),
    )
    op.add_column(
        "creative_docs",
        sa.Column("revision_note", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("creative_docs", "revision_note")
    op.drop_column("creative_docs", "created_by")
    op.drop_column("creative_docs", "parent_id")
