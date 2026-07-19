"""g4_approval_targets

Revision ID: 79fa3959d12f
Revises: 4bbd7db38ad2
Create Date: 2026-07-19 20:29:15.624582
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '79fa3959d12f'
down_revision: Union[str, None] = '4bbd7db38ad2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'approvals',
        sa.Column('targets', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('approvals', 'targets')
