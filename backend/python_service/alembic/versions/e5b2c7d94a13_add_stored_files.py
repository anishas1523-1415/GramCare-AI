"""Add stored_files table for database-backed upload storage

Uploads previously required Cloudinary credentials; without them the API
accepted license scans, profile photos and recall notices and silently
discarded them. CloudinaryClient now falls back to writing a row here and
serving it from GET /api/v1/files/{token}.

Revision ID: e5b2c7d94a13
Revises: d3f8a91c5e02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5b2c7d94a13'
down_revision: Union[str, Sequence[str], None] = 'd3f8a91c5e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stored_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(), nullable=True),
        sa.Column('folder', sa.String(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('data', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_stored_files_id'), 'stored_files', ['id'], unique=False)
    op.create_index(op.f('ix_stored_files_token'), 'stored_files', ['token'], unique=True)
    op.create_index(op.f('ix_stored_files_folder'), 'stored_files', ['folder'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stored_files_folder'), table_name='stored_files')
    op.drop_index(op.f('ix_stored_files_token'), table_name='stored_files')
    op.drop_index(op.f('ix_stored_files_id'), table_name='stored_files')
    op.drop_table('stored_files')
