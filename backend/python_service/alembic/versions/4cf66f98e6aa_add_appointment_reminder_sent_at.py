"""add appointment reminder_sent_at

Revision ID: 4cf66f98e6aa
Revises: c7a3f0e91d24
Create Date: 2026-07-18 08:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cf66f98e6aa'
down_revision: Union[str, Sequence[str], None] = 'c7a3f0e91d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('appointments', sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('appointments', 'reminder_sent_at')
