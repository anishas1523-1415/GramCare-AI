"""doctor verification, hospital self-registration, government whitelist

Revision ID: 793f2f77e7d4
Revises: 8bcddc16f3a2
Create Date: 2026-07-13 09:15:37.546798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '793f2f77e7d4'
down_revision: Union[str, Sequence[str], None] = '8bcddc16f3a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('authorized_government_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_authorized_government_emails_email'), 'authorized_government_emails', ['email'], unique=True)
    op.create_index(op.f('ix_authorized_government_emails_id'), 'authorized_government_emails', ['id'], unique=False)

    # batch_alter_table (not bare op.add_column/create_foreign_key) is
    # required for the FK-bearing columns below — SQLite has no ALTER-table
    # constraint support outside batch mode, and this project's test suite
    # (tests/test_migrations.py) runs this exact chain against SQLite. See
    # alembic/versions/7a1c4e9f2b30_phase1_contract_foundation.py for the
    # established pattern this follows.
    with op.batch_alter_table('doctor_profiles') as batch:
        batch.add_column(sa.Column('license_number', sa.String(), nullable=True))
        batch.add_column(sa.Column('license_document_url', sa.String(), nullable=True))
        batch.add_column(sa.Column('service_hours', sa.String(), nullable=True))
        batch.add_column(sa.Column('verification_status', sa.String(), nullable=True))
        batch.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
        batch.add_column(sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('reviewed_at', sa.DateTime(), nullable=True))
        batch.create_index(op.f('ix_doctor_profiles_license_number'), ['license_number'], unique=True)
        batch.create_index(op.f('ix_doctor_profiles_verification_status'), ['verification_status'], unique=False)
        batch.create_foreign_key('fk_doctor_profiles_reviewed_by', 'users', ['reviewed_by_user_id'], ['id'])

    with op.batch_alter_table('hospitals') as batch:
        batch.add_column(sa.Column('owner_user_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('established_year', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('service_timing', sa.String(), nullable=True))
        batch.add_column(sa.Column('specializations', sa.String(), nullable=True))
        batch.add_column(sa.Column('license_number', sa.String(), nullable=True))
        batch.add_column(sa.Column('license_document_url', sa.String(), nullable=True))
        batch.create_index(op.f('ix_hospitals_owner_user_id'), ['owner_user_id'], unique=True)
        batch.create_foreign_key('fk_hospitals_owner', 'users', ['owner_user_id'], ['id'])

    # Existing doctor accounts predate the approval workflow entirely —
    # defaulting them to APPROVED avoids retroactively locking out every
    # doctor who registered before this migration. Only genuinely NEW
    # applications (created after this point) start PENDING (models.py's
    # column default handles that at the ORM level going forward).
    op.execute("UPDATE doctor_profiles SET verification_status = 'APPROVED' WHERE verification_status IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('hospitals') as batch:
        batch.drop_constraint('fk_hospitals_owner', type_='foreignkey')
        batch.drop_index(op.f('ix_hospitals_owner_user_id'))
        batch.drop_column('license_document_url')
        batch.drop_column('license_number')
        batch.drop_column('specializations')
        batch.drop_column('service_timing')
        batch.drop_column('established_year')
        batch.drop_column('owner_user_id')

    with op.batch_alter_table('doctor_profiles') as batch:
        batch.drop_constraint('fk_doctor_profiles_reviewed_by', type_='foreignkey')
        batch.drop_index(op.f('ix_doctor_profiles_verification_status'))
        batch.drop_index(op.f('ix_doctor_profiles_license_number'))
        batch.drop_column('reviewed_at')
        batch.drop_column('reviewed_by_user_id')
        batch.drop_column('rejection_reason')
        batch.drop_column('verification_status')
        batch.drop_column('service_hours')
        batch.drop_column('license_document_url')
        batch.drop_column('license_number')

    op.drop_index(op.f('ix_authorized_government_emails_id'), table_name='authorized_government_emails')
    op.drop_index(op.f('ix_authorized_government_emails_email'), table_name='authorized_government_emails')
    op.drop_table('authorized_government_emails')
