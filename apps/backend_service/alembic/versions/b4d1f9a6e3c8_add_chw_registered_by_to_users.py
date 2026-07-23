"""add registered_by_chw_id to users (CHW tooling)

Revision ID: b4d1f9a6e3c8
Revises: 5ab05c023561
Create Date: 2026-07-19 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d1f9a6e3c8'
down_revision: Union[str, Sequence[str], None] = '35a8baf304c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table (not bare op.add_column/create_foreign_key) is
    # required for the FK-bearing column below — SQLite has no ALTER-table
    # constraint support outside batch mode, and this project's test suite
    # (tests/test_migrations.py) runs this exact chain against SQLite. See
    # alembic/versions/793f2f77e7d4_doctor_verification_hospital_self_.py for
    # the established pattern this follows.
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('registered_by_chw_id', sa.Integer(), nullable=True))
        batch.create_index(op.f('ix_users_registered_by_chw_id'), ['registered_by_chw_id'], unique=False)
        batch.create_foreign_key('fk_users_registered_by_chw', 'users', ['registered_by_chw_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('fk_users_registered_by_chw', type_='foreignkey')
        batch.drop_index(op.f('ix_users_registered_by_chw_id'))
        batch.drop_column('registered_by_chw_id')
