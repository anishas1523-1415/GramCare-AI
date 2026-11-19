"""index the columns the tenant-scoping filters select on

Experiment G's remediations added two ownership filters to hot paths:

  GET /sos/active     filters emergency_sos.assigned_hospital_id
  GET /ehr/records    filters prescriptions.doctor_id

The PostgreSQL validation run (research/experiments/exp_g) found neither
column indexed, so both scoped queries were sequential scans. One of them is
the emergency desk's poll, which is the single endpoint in this system that
must never be slow.

This migration is index-only: it adds no column, drops nothing and changes no
data, so it is safe to apply to a live database. Note that Alembic is not run
automatically on deploy in this project — apply it by hand.

Revision ID: d1f7c3b9e205
Revises: b8d4f1a70c93
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "d1f7c3b9e205"
down_revision = "b8d4f1a70c93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set()
    inspector = sa.inspect(bind)
    for table in ("emergency_sos", "prescriptions"):
        try:
            for ix in inspector.get_indexes(table):
                existing.add(ix["name"])
        except Exception:
            # Table absent on a partially migrated database: create_index
            # below will raise with a clearer message than we could.
            pass

    if "ix_emergency_sos_assigned_hospital_id" not in existing:
        op.create_index(
            "ix_emergency_sos_assigned_hospital_id",
            "emergency_sos",
            ["assigned_hospital_id"],
        )
    if "ix_prescriptions_doctor_id" not in existing:
        op.create_index(
            "ix_prescriptions_doctor_id",
            "prescriptions",
            ["doctor_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_prescriptions_doctor_id", table_name="prescriptions")
    op.drop_index(
        "ix_emergency_sos_assigned_hospital_id", table_name="emergency_sos"
    )
