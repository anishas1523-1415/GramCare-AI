"""add referral network

Revision ID: 35a8baf304c1
Revises: 5ab05c023561
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35a8baf304c1'
down_revision: Union[str, Sequence[str], None] = '5ab05c023561'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('referrals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('family_profile_id', sa.Integer(), nullable=True),
    sa.Column('referring_doctor_id', sa.Integer(), nullable=True),
    sa.Column('referred_to_doctor_id', sa.Integer(), nullable=True),
    sa.Column('specialty', sa.String(), nullable=True),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['family_profile_id'], ['family_profiles.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['referred_to_doctor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['referring_doctor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_referrals_id'), 'referrals', ['id'], unique=False)
    op.create_index(op.f('ix_referrals_patient_id'), 'referrals', ['patient_id'], unique=False)
    op.create_index(op.f('ix_referrals_referring_doctor_id'), 'referrals', ['referring_doctor_id'], unique=False)
    op.create_index(op.f('ix_referrals_referred_to_doctor_id'), 'referrals', ['referred_to_doctor_id'], unique=False)
    op.create_index(op.f('ix_referrals_specialty'), 'referrals', ['specialty'], unique=False)
    op.create_index(op.f('ix_referrals_status'), 'referrals', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_referrals_status'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_specialty'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referred_to_doctor_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referring_doctor_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_patient_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_id'), table_name='referrals')
    op.drop_table('referrals')
