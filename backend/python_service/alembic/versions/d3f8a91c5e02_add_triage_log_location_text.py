"""Add missing triage_logs.location_text column

The TriageLog model has declared this column since Community Health
Intelligence was built (location_text = Column(String, nullable=True,
index=True) — "Used for community health heatmaps"), but no migration
ever actually added it to the database. Every query touching the full
TriageLog entity (GET /analytics/overview's db.query(models.TriageLog)
calls) has been throwing psycopg2.errors.UndefinedColumn on every single
request since — confirmed via the live production traceback.

Revision ID: d3f8a91c5e02
Revises: b4d1f9a6e3c8
Create Date: 2026-09-14 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f8a91c5e02'
down_revision: Union[str, Sequence[str], None] = 'b4d1f9a6e3c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('triage_logs', sa.Column('location_text', sa.String(), nullable=True))
    op.create_index(op.f('ix_triage_logs_location_text'), 'triage_logs', ['location_text'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_triage_logs_location_text'), table_name='triage_logs')
    op.drop_column('triage_logs', 'location_text')
