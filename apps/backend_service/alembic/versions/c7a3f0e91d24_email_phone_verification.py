"""email verification, phone otp verification

Revision ID: c7a3f0e91d24
Revises: 793f2f77e7d4
Create Date: 2026-07-14 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a3f0e91d24'
down_revision: Union[str, Sequence[str], None] = '793f2f77e7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('token', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_email_verification_tokens_user'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_verification_tokens_id'), 'email_verification_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_email_verification_tokens_user_id'), 'email_verification_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_email_verification_tokens_token'), 'email_verification_tokens', ['token'], unique=True)

    op.create_table('phone_otps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('otp_code', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_phone_otps_id'), 'phone_otps', ['id'], unique=False)
    op.create_index(op.f('ix_phone_otps_phone'), 'phone_otps', ['phone'], unique=False)

    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('is_verified', sa.Boolean(), nullable=True))
        batch.add_column(sa.Column('phone', sa.String(), nullable=True))
        batch.add_column(sa.Column('phone_verified', sa.Boolean(), nullable=True))

    # Every account that existed before this migration predates the
    # verify-before-login gate entirely — defaulting them to verified
    # avoids retroactively locking out everyone already registered. Only
    # genuinely NEW accounts (created after this point) start unverified
    # (models.py's column default handles that at the ORM level going
    # forward). Same backfill pattern as the doctor verification_status
    # migration before this one.
    # TRUE/FALSE rather than 1/0: SQLite treats booleans as integers and
    # accepts either, but real Postgres (production) is strict and rejects
    # an integer literal against a boolean column outright.
    op.execute("UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL")
    op.execute("UPDATE users SET phone_verified = FALSE WHERE phone_verified IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch:
        batch.drop_column('phone_verified')
        batch.drop_column('phone')
        batch.drop_column('is_verified')

    op.drop_index(op.f('ix_phone_otps_phone'), table_name='phone_otps')
    op.drop_index(op.f('ix_phone_otps_id'), table_name='phone_otps')
    op.drop_table('phone_otps')

    op.drop_index(op.f('ix_email_verification_tokens_token'), table_name='email_verification_tokens')
    op.drop_index(op.f('ix_email_verification_tokens_user_id'), table_name='email_verification_tokens')
    op.drop_index(op.f('ix_email_verification_tokens_id'), table_name='email_verification_tokens')
    op.drop_table('email_verification_tokens')
