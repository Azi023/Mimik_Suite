"""g1_brand_assets

Revision ID: 4bbd7db38ad2
Revises: b08ff128c47c
Create Date: 2026-07-19 17:13:31.238553
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4bbd7db38ad2'
down_revision: Union[str, None] = 'b08ff128c47c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'brand_assets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('brand_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('mime', sa.String(), nullable=False),
        sa.Column('local_path', sa.String(), nullable=True),
        sa.Column('drive_file_id', sa.String(), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column('license', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('study', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_brand_assets_tenant_id'), 'brand_assets', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_brand_assets_client_id'), 'brand_assets', ['client_id'], unique=False)
    op.create_index(op.f('ix_brand_assets_brand_id'), 'brand_assets', ['brand_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_brand_assets_brand_id'), table_name='brand_assets')
    op.drop_index(op.f('ix_brand_assets_client_id'), table_name='brand_assets')
    op.drop_index(op.f('ix_brand_assets_tenant_id'), table_name='brand_assets')
    op.drop_table('brand_assets')
