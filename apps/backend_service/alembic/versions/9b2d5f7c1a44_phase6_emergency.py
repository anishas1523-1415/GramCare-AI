"""Phase 6 — emergency contacts + SOS escalation/voice-note

Revision ID: 9b2d5f7c1a44
Revises: 7a1c4e9f2b30
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b2d5f7c1a44"
down_revision: Union[str, Sequence[str], None] = "7a1c4e9f2b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("relation", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emergency_contacts_id"), "emergency_contacts", ["id"])
    op.create_index(op.f("ix_emergency_contacts_user_id"), "emergency_contacts", ["user_id"])

    with op.batch_alter_table("emergency_sos") as batch:
        batch.add_column(sa.Column("voice_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("escalation_level", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("assigned_hospital_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_sos_hospital", "hospitals", ["assigned_hospital_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("emergency_sos") as batch:
        batch.drop_constraint("fk_sos_hospital", type_="foreignkey")
        batch.drop_column("assigned_hospital_id")
        batch.drop_column("escalation_level")
        batch.drop_column("voice_note")
    op.drop_index(op.f("ix_emergency_contacts_user_id"), table_name="emergency_contacts")
    op.drop_index(op.f("ix_emergency_contacts_id"), table_name="emergency_contacts")
    op.drop_table("emergency_contacts")
