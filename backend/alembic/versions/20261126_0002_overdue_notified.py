"""remember when overdue alerts were sent

Revision ID: 0002_overdue_notified
Revises: 0001_initial
Create Date: 2026-11-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_overdue_notified"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shipments", sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shipments", "overdue_notified_at")
    op.drop_column("purchase_orders", "overdue_notified_at")
