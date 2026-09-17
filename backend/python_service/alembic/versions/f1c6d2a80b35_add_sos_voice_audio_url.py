"""Add emergency_sos.voice_audio_url for the patient's real recording

voice_note only ever held the speech-to-text transcript. A responder needs
the recording itself: distress, breathlessness, someone else speaking, or a
dialect the recogniser mangled are all lost in a transcript.

Revision ID: f1c6d2a80b35
Revises: e5b2c7d94a13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1c6d2a80b35'
down_revision: Union[str, Sequence[str], None] = 'e5b2c7d94a13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent for the same reason as e5b2c7d94a13: this column is applied
    # directly to production ahead of the deploy that carries the migration,
    # and startCommand runs `alembic upgrade head` on every boot — a hard
    # failure here takes the whole service down, not just the migration.
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('emergency_sos')}
    if 'voice_audio_url' in columns:
        return
    op.add_column('emergency_sos', sa.Column('voice_audio_url', sa.String(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('emergency_sos')}
    if 'voice_audio_url' not in columns:
        return
    op.drop_column('emergency_sos', 'voice_audio_url')
