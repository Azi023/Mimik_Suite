"""user_account_client_scopes

Revision ID: 27bc3b786ef3
Revises: cb072f89d251
Create Date: 2026-07-20 20:54:58.441992
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '27bc3b786ef3'
down_revision: Union[str, None] = 'cb072f89d251'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Empty list = ALL clients (default, current behavior); non-empty = an assigned subset.
    op.add_column(
        "user_accounts",
        sa.Column("client_scopes", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "client_scopes")
