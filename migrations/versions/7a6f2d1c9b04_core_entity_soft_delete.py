"""Add audited soft-delete state to the operator's core entities.

Revision ID: 7a6f2d1c9b04
Revises: 3d91b84ad827
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a6f2d1c9b04"
down_revision: Union[str, None] = "3d91b84ad827"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "clients",
    "brands",
    "briefs",
    "creative_docs",
    "tasks",
    "brand_assets",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(table, sa.Column("deleted_by", sa.JSON(), nullable=True))
    op.drop_constraint("uq_clients_tenant_email", "clients", type_="unique")
    op.create_index(
        "uq_clients_tenant_email",
        "clients",
        ["tenant_id", "contact_email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_clients_tenant_email", table_name="clients")
    op.create_unique_constraint(
        "uq_clients_tenant_email",
        "clients",
        ["tenant_id", "contact_email"],
    )
    for table in reversed(_TABLES):
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")
