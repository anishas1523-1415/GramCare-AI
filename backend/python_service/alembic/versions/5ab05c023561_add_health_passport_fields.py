"""add health passport fields to users

Revision ID: 5ab05c023561
Revises: 4cf66f98e6aa
Create Date: 2026-07-19 05:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ab05c023561'
down_revision: Union[str, Sequence[str], None] = '4cf66f98e6aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('blood_group', sa.String(), nullable=True))
    op.add_column('users', sa.Column('allergies', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('chronic_conditions', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('passport_token', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_passport_token'), 'users', ['passport_token'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_passport_token'), table_name='users')
    op.drop_column('users', 'passport_token')
    op.drop_column('users', 'chronic_conditions')
    op.drop_column('users', 'allergies')
    op.drop_column('users', 'blood_group')
