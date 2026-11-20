"""scope ehr_records.client_uuid uniqueness to the patient

Experiment A (docs/research/experiments/exp_a) measured what the table-wide
unique index on client_uuid cost:

    If patient B submitted a client_uuid that patient A had already used, the
    dedupe pre-check matched A's row, classified B's record as a duplicate,
    skipped it, and returned the uuid in `duplicates[]`. B's client treats
    `duplicates[]` as success, so B's phone marked the record synced. Nothing
    was stored for B and nobody was told.

    Measured rate: 30 of 30 trials. Silent cross-tenant clinical data loss.

This migration replaces the global unique index with:

  * a plain (non-unique) index on client_uuid, which the lookups still need
  * a UNIQUE constraint on (patient_id, client_uuid)

so A's and B's records coexist while each patient's own retries continue to
deduplicate. The matching predicate change is in modules/ehr_sync/router.py;
both are needed.

SAFETY
------
This alters a unique constraint on a live table, so it refuses rather than
corrupts:

  * If any client_uuid is already used by more than one patient, the
    composite constraint cannot be created. That cannot happen while the old
    global index exists, but a database restored from elsewhere might differ,
    so it is checked and raised with a clear message instead of failing on a
    cryptic index error.
  * Every step inspects before acting, so a partially applied state is
    recoverable by re-running.
  * NULL client_uuid rows (records created server-side, e.g. doctor-issued
    prescriptions) are unaffected: PostgreSQL treats NULLs as distinct in a
    unique constraint, so any number of them coexist.

render.yaml runs `alembic upgrade head` in the service start command, so a
deploy applies this automatically. It runs BEFORE uvicorn, which is why it is
written to fail loudly on a real data problem rather than half-apply.

Revision ID: e4a9d2c7b118
Revises: d1f7c3b9e205
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e4a9d2c7b118"
down_revision = "d1f7c3b9e205"
branch_labels = None
depends_on = None

OLD_UNIQUE_INDEX = "ix_ehr_records_client_uuid"
NEW_CONSTRAINT = "uq_ehr_records_patient_client_uuid"


def _index_names(bind, table):
    try:
        return {ix["name"]: ix for ix in sa.inspect(bind).get_indexes(table)}
    except Exception:
        return {}


def _constraint_names(bind, table):
    try:
        return {c["name"] for c in
                sa.inspect(bind).get_unique_constraints(table)}
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Refuse if the data cannot satisfy the new constraint.
    conflicts = bind.execute(sa.text("""
        SELECT count(*) FROM (
            SELECT client_uuid
            FROM ehr_records
            WHERE client_uuid IS NOT NULL
            GROUP BY client_uuid
            HAVING count(DISTINCT patient_id) > 1
        ) AS t
    """)).scalar()
    if conflicts:
        raise RuntimeError(
            "%d client_uuid value(s) are shared by more than one patient, so "
            "UNIQUE (patient_id, client_uuid) cannot be created. Resolve the "
            "duplicates first:\n"
            "  SELECT client_uuid, array_agg(DISTINCT patient_id) "
            "FROM ehr_records WHERE client_uuid IS NOT NULL "
            "GROUP BY client_uuid HAVING count(DISTINCT patient_id) > 1;"
            % conflicts
        )

    indexes = _index_names(bind, "ehr_records")
    constraints = _constraint_names(bind, "ehr_records")

    # 2. Drop the table-wide unique index first.
    #
    #    Order matters, and differs from the obvious one. SQLite has no ALTER
    #    for constraints, so step 3 goes through Alembic's batch mode, which
    #    recreates the table by copy-and-move. Dropping the old index before
    #    that avoids a name collision during the copy. PostgreSQL executes
    #    both as plain ALTERs and does not care about the order.
    if OLD_UNIQUE_INDEX in indexes:
        op.drop_index(OLD_UNIQUE_INDEX, table_name="ehr_records")

    # 3. Add the per-patient uniqueness guarantee.
    #
    #    batch_alter_table so this works on SQLite (the project's test suite
    #    runs the whole chain on SQLite) as well as PostgreSQL.
    if NEW_CONSTRAINT not in constraints:
        with op.batch_alter_table("ehr_records") as batch_op:
            batch_op.create_unique_constraint(
                NEW_CONSTRAINT, ["patient_id", "client_uuid"]
            )

    # 4. Re-create the client_uuid index, non-unique, for the lookups.
    indexes = _index_names(bind, "ehr_records")
    if OLD_UNIQUE_INDEX not in indexes:
        op.create_index(OLD_UNIQUE_INDEX, "ehr_records", ["client_uuid"],
                        unique=False)


def downgrade() -> None:
    """Restore the table-wide unique index.

    This re-introduces the data-loss behaviour the upgrade fixed, and it fails
    if any client_uuid is now used by more than one patient — which is exactly
    the state the upgrade makes possible. There is no safe automatic way to
    choose which patient's record to discard, so it refuses.
    """
    bind = op.get_bind()
    dupes = bind.execute(sa.text("""
        SELECT count(*) FROM (
            SELECT client_uuid FROM ehr_records
            WHERE client_uuid IS NOT NULL
            GROUP BY client_uuid HAVING count(*) > 1
        ) AS t
    """)).scalar()
    if dupes:
        raise RuntimeError(
            "%d client_uuid value(s) now appear on more than one row, so the "
            "table-wide unique index cannot be restored without deleting "
            "patient records. Downgrade refused." % dupes
        )

    indexes = _index_names(bind, "ehr_records")
    constraints = _constraint_names(bind, "ehr_records")

    if OLD_UNIQUE_INDEX in indexes:
        op.drop_index(OLD_UNIQUE_INDEX, table_name="ehr_records")
    if NEW_CONSTRAINT in constraints:
        with op.batch_alter_table("ehr_records") as batch_op:
            batch_op.drop_constraint(NEW_CONSTRAINT, type_="unique")
    op.create_index(OLD_UNIQUE_INDEX, "ehr_records", ["client_uuid"],
                    unique=True)
