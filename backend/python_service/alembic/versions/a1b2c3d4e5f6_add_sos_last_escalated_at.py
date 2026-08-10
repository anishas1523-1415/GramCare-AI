"""Phase 6.1 — preserve SOS audit trail with last_escalated_at

Adds emergency_sos.last_escalated_at so the escalation clock no longer
overwrites created_at (the true creation time is kept for the medical-audit
trail).

Revision ID: a1b2c3d4e5f6
Revises: 9b2d5f7c1a44
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9b2d5f7c1a44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("emergency_sos") as batch:
        batch.add_column(sa.Column("last_escalated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("emergency_sos") as batch:
        batch.drop_column("last_escalated_at")
