"""add payment idempotency_key

Revision ID: c2f4a9d1e6b7
Revises: 8757c24a7b38
Create Date: 2026-07-04 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f4a9d1e6b7'
down_revision: Union[str, Sequence[str], None] = '8757c24a7b38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('payments') as batch_op:
        batch_op.add_column(sa.Column('idempotency_key', sa.String(), nullable=True))
    op.create_index(
        op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=False,
    )
    # Partial unique index: a retried create-order call with the same
    # (patient_id, idempotency_key) must resolve to the same row, but rows
    # where idempotency_key is NULL (older clients, or callers that don't
    # send one) must never collide with each other.
    op.create_index(
        'ix_payments_patient_idempotency_unique',
        'payments',
        ['patient_id', 'idempotency_key'],
        unique=True,
        sqlite_where=sa.text('idempotency_key IS NOT NULL'),
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_payments_patient_idempotency_unique', table_name='payments')
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_column('idempotency_key')
