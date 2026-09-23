"""Gate hospitals behind government review before SOS can route to them

Any account registered with role=HOSPITAL was immediately eligible to be
sent a patient's name, GPS coordinates and voice recording, because
_nearest_hospital() selected from every row with no approval gate at all.

Revision ID: b8d4f1a70c93
Revises: a7e3b1c52f08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d4f1a70c93'
down_revision: Union[str, Sequence[str], None] = 'a7e3b1c52f08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: applied directly to production ahead of the deploy that
    # carries it, and startCommand runs `alembic upgrade head` on every boot.
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('hospitals')}
    if 'verification_status' not in columns:
        # server_default so rows created by an older running instance during
        # the deploy window are PENDING rather than NULL — a NULL would fail
        # the == "APPROVED" filter anyway, but explicit beats incidental for
        # the column that decides who sees an emergency.
        op.add_column('hospitals', sa.Column(
            'verification_status', sa.String(), nullable=True, server_default='PENDING'))
        op.create_index('ix_hospitals_verification_status', 'hospitals', ['verification_status'])
    if 'verification_notes' not in columns:
        op.add_column('hospitals', sa.Column('verification_notes', sa.String(), nullable=True))
    if 'reviewed_by_user_id' not in columns:
        op.add_column('hospitals', sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True))
    if 'reviewed_at' not in columns:
        op.add_column('hospitals', sa.Column('reviewed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('hospitals')}
    if 'verification_status' in columns:
        op.drop_index('ix_hospitals_verification_status', table_name='hospitals')
        op.drop_column('hospitals', 'verification_status')
    for col in ('verification_notes', 'reviewed_by_user_id', 'reviewed_at'):
        if col in columns:
            op.drop_column('hospitals', col)
