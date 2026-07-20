"""invitations

Revision ID: cb072f89d251
Revises: 8281453f4476
Create Date: 2026-07-20 20:24:35.106444
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cb072f89d251'
down_revision: Union[str, None] = '8281453f4476'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('client_scopes', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('invited_by', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_invitations_tenant_id'), 'invitations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_invitations_email'), 'invitations', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_invitations_email'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_tenant_id'), table_name='invitations')
    op.drop_table('invitations')
