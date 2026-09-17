"""Add emergency_sos.public_token for the family tracking link

Emergency contacts are phone numbers, not accounts. Without a capability
token there is no way to show them the patient's location, the responding
hospital's distance and ETA, or the voice recording — the SMS could only
ever carry a map pin.

Revision ID: a7e3b1c52f08
Revises: f1c6d2a80b35
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7e3b1c52f08'
down_revision: Union[str, Sequence[str], None] = 'f1c6d2a80b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: applied directly to production ahead of the deploy that
    # carries it, and startCommand runs `alembic upgrade head` on every boot.
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('emergency_sos')}
    if 'public_token' in columns:
        return
    op.add_column('emergency_sos', sa.Column('public_token', sa.String(), nullable=True))
    op.create_index('ix_emergency_sos_public_token', 'emergency_sos', ['public_token'], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('emergency_sos')}
    if 'public_token' not in columns:
        return
    op.drop_index('ix_emergency_sos_public_token', table_name='emergency_sos')
    op.drop_column('emergency_sos', 'public_token')
