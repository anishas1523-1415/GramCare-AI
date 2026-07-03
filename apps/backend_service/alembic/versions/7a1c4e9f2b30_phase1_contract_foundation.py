"""Phase 1 — contract & data-model foundation

New entities: doctor_profiles, availability_slots, payments, pharmacies,
hospitals. Reworked: ehr_records (int FK patient_id, family scoping,
structured payload, client_uuid for idempotent sync), pharmacy_inventory
(real FK, expiry/batch/generic_group), iot_vitals (int FK patient_id).
Family scoping columns added to appointments, prescriptions, emergency_sos,
triage_logs.

The ehr_records / pharmacy_inventory / iot_vitals changes are table
recreations (SQLite-safe batch style). Pre-pilot, existing demo rows in
those three tables are NOT migrated — the string patient_id values were
free-form legacy tags with no referential guarantee. This is the documented
destructive-reset decision from the roadmap (Phase 1, "Risks").

Revision ID: 7a1c4e9f2b30
Revises: 0d9255b12a10
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a1c4e9f2b30"
down_revision: Union[str, Sequence[str], None] = "0d9255b12a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables -------------------------------------------------------
    op.create_table(
        "doctor_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("specialty", sa.String(), nullable=True),
        sa.Column("qualifications", sa.String(), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("consultation_fee", sa.Float(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("languages", sa.String(), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_doctor_profiles_id"), "doctor_profiles", ["id"])
    op.create_index(op.f("ix_doctor_profiles_specialty"), "doctor_profiles", ["specialty"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("gateway", sa.String(), nullable=True),
        sa.Column("gateway_payment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_payments_id"), "payments", ["id"])
    op.create_index(op.f("ix_payments_status"), "payments", ["status"])

    op.create_table(
        "pharmacies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id"),
    )
    op.create_index(op.f("ix_pharmacies_id"), "pharmacies", ["id"])
    op.create_index(op.f("ix_pharmacies_lat"), "pharmacies", ["lat"])
    op.create_index(op.f("ix_pharmacies_lng"), "pharmacies", ["lng"])

    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("emergency_desk_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["emergency_desk_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("emergency_desk_user_id"),
    )
    op.create_index(op.f("ix_hospitals_id"), "hospitals", ["id"])

    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_profile_id", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("is_booked", sa.Boolean(), nullable=True),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["doctor_profile_id"], ["doctor_profiles.id"]),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_profile_id", "start_time", name="uq_slot_doctor_start"),
    )
    op.create_index(op.f("ix_availability_slots_id"), "availability_slots", ["id"])
    op.create_index(op.f("ix_availability_slots_start_time"), "availability_slots", ["start_time"])
    op.create_index(op.f("ix_availability_slots_doctor_profile_id"), "availability_slots", ["doctor_profile_id"])

    # --- Family scoping / payment link on existing tables -----------------
    with op.batch_alter_table("appointments") as batch:
        batch.add_column(sa.Column("family_profile_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("payment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_appt_family", "family_profiles", ["family_profile_id"], ["id"])
        batch.create_foreign_key("fk_appt_payment", "payments", ["payment_id"], ["id"])

    with op.batch_alter_table("prescriptions") as batch:
        batch.add_column(sa.Column("family_profile_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("fulfilled_by_pharmacy_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_rx_family", "family_profiles", ["family_profile_id"], ["id"])
        batch.create_foreign_key("fk_rx_pharmacy", "pharmacies", ["fulfilled_by_pharmacy_id"], ["id"])

    with op.batch_alter_table("emergency_sos") as batch:
        batch.add_column(sa.Column("family_profile_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_sos_family", "family_profiles", ["family_profile_id"], ["id"])

    with op.batch_alter_table("triage_logs") as batch:
        batch.add_column(sa.Column("family_profile_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_triage_family", "family_profiles", ["family_profile_id"], ["id"])

    with op.batch_alter_table("family_profiles") as batch:
        batch.add_column(sa.Column("photo_url", sa.String(), nullable=True))
        batch.add_column(sa.Column("color_tag", sa.String(), nullable=True))

    # --- Destructive recreations (documented above) ------------------------
    op.drop_index(op.f("ix_iot_vitals_patient_id"), table_name="iot_vitals")
    op.drop_index(op.f("ix_iot_vitals_id"), table_name="iot_vitals")
    op.drop_table("iot_vitals")
    op.create_table(
        "iot_vitals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("family_profile_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.String(), nullable=True),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["family_profile_id"], ["family_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_iot_vitals_id"), "iot_vitals", ["id"])
    op.create_index(op.f("ix_iot_vitals_patient_id"), "iot_vitals", ["patient_id"])

    op.drop_table("ehr_records")
    op.create_table(
        "ehr_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("family_profile_id", sa.Integer(), nullable=True),
        sa.Column("record_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("doctor_name", sa.String(), nullable=True),
        sa.Column("client_uuid", sa.String(), nullable=True),
        sa.Column("record_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["family_profile_id"], ["family_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_uuid"),
    )
    op.create_index(op.f("ix_ehr_records_id"), "ehr_records", ["id"])
    op.create_index(op.f("ix_ehr_records_patient_id"), "ehr_records", ["patient_id"])
    op.create_index(op.f("ix_ehr_records_family_profile_id"), "ehr_records", ["family_profile_id"])
    op.create_index(op.f("ix_ehr_records_record_type"), "ehr_records", ["record_type"])
    op.create_index(op.f("ix_ehr_records_client_uuid"), "ehr_records", ["client_uuid"])

    op.drop_table("pharmacy_inventory")
    op.create_table(
        "pharmacy_inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pharmacy_id", sa.Integer(), nullable=True),
        sa.Column("medicine_name", sa.String(), nullable=True),
        sa.Column("generic_group", sa.String(), nullable=True),
        sa.Column("stock_count", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("requires_prescription", sa.Boolean(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("batch_number", sa.String(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["pharmacy_id"], ["pharmacies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pharmacy_inventory_id"), "pharmacy_inventory", ["id"])
    op.create_index(op.f("ix_pharmacy_inventory_pharmacy_id"), "pharmacy_inventory", ["pharmacy_id"])
    op.create_index(op.f("ix_pharmacy_inventory_medicine_name"), "pharmacy_inventory", ["medicine_name"])
    op.create_index(op.f("ix_pharmacy_inventory_generic_group"), "pharmacy_inventory", ["generic_group"])


def downgrade() -> None:
    # Reverse of the recreations restores the legacy string-keyed shapes.
    op.drop_table("pharmacy_inventory")
    op.create_table(
        "pharmacy_inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pharmacy_id", sa.String(), nullable=True),
        sa.Column("medicine_name", sa.String(), nullable=True),
        sa.Column("stock_count", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("requires_prescription", sa.Boolean(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("ehr_records")
    op.create_table(
        "ehr_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=True),
        sa.Column("record_type", sa.String(), nullable=True),
        sa.Column("content", sa.String(), nullable=True),
        sa.Column("doctor_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("iot_vitals")
    op.create_table(
        "iot_vitals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=True),
        sa.Column("device_id", sa.String(), nullable=True),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("family_profiles") as batch:
        batch.drop_column("photo_url")
        batch.drop_column("color_tag")
    with op.batch_alter_table("triage_logs") as batch:
        batch.drop_constraint("fk_triage_family", type_="foreignkey")
        batch.drop_column("family_profile_id")
    with op.batch_alter_table("emergency_sos") as batch:
        batch.drop_constraint("fk_sos_family", type_="foreignkey")
        batch.drop_column("family_profile_id")
    with op.batch_alter_table("prescriptions") as batch:
        batch.drop_constraint("fk_rx_pharmacy", type_="foreignkey")
        batch.drop_constraint("fk_rx_family", type_="foreignkey")
        batch.drop_column("fulfilled_by_pharmacy_id")
        batch.drop_column("family_profile_id")
    with op.batch_alter_table("appointments") as batch:
        batch.drop_constraint("fk_appt_payment", type_="foreignkey")
        batch.drop_constraint("fk_appt_family", type_="foreignkey")
        batch.drop_column("payment_id")
        batch.drop_column("family_profile_id")

    op.drop_table("availability_slots")
    op.drop_table("hospitals")
    op.drop_table("pharmacies")
    op.drop_table("payments")
    op.drop_index(op.f("ix_doctor_profiles_specialty"), table_name="doctor_profiles")
    op.drop_index(op.f("ix_doctor_profiles_id"), table_name="doctor_profiles")
    op.drop_table("doctor_profiles")
