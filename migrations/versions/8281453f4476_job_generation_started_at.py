"""job generation_started_at

Revision ID: 8281453f4476
Revises: 79fa3959d12f
Create Date: 2026-07-20 15:57:55.887418
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8281453f4476'
down_revision: Union[str, None] = '79fa3959d12f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('generation_started_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'generation_started_at')
