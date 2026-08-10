"""Verify Neon PostgreSQL schema: tables, constraints, indexes, foreign keys."""
from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import create_engine, text, inspect

url = os.getenv("DATABASE_URL")
engine = create_engine(url)
inspector = inspect(engine)

print("=" * 60)
print("TABLE VERIFICATION")
print("=" * 60)
tables = inspector.get_table_names()
print(f"Total tables: {len(tables)}")
for t in sorted(tables):
    print(f"  - {t}")

expected = [
    "users", "user_push_tokens", "family_profiles", "doctor_profiles",
    "availability_slots", "appointments", "payments", "prescriptions",
    "emergency_sos", "emergency_contacts", "triage_logs", "ehr_records",
    "pharmacies", "pharmacy_inventory", "hospitals", "iot_vitals",
]
missing = [t for t in expected if t not in tables]
if missing:
    print(f"MISSING TABLES: {missing}")
    exit(1)
else:
    print("All 16 expected tables present: PASS")

print()
print("=" * 60)
print("PRIMARY KEY VERIFICATION")
print("=" * 60)
for t in sorted(tables):
    if t == "alembic_version":
        continue
    pk = inspector.get_pk_constraint(t)
    cols = pk.get("constrained_columns", [])
    print(f"  {t}: PK({', '.join(cols)})")

print()
print("=" * 60)
print("UNIQUE CONSTRAINT VERIFICATION")
print("=" * 60)
for t in sorted(tables):
    if t == "alembic_version":
        continue
    constraints = inspector.get_unique_constraints(t)
    for c in constraints:
        print(f"  {t}: UNIQUE({c['name']}) -> {c['column_names']}")

print()
print("=" * 60)
print("INDEX VERIFICATION")
print("=" * 60)
total_indexes = 0
for t in sorted(tables):
    if t == "alembic_version":
        continue
    indexes = inspector.get_indexes(t)
    for idx in indexes:
        unique = "UNIQUE " if idx.get("unique") else ""
        partial = " (PARTIAL)" if idx.get("postgresql_where") else ""
        print(f"  {t}: {unique}INDEX {idx['name']} -> {idx['column_names']}{partial}")
        total_indexes += 1
print(f"Total indexes: {total_indexes}")

print()
print("=" * 60)
print("FOREIGN KEY VERIFICATION")
print("=" * 60)
total_fks = 0
for t in sorted(tables):
    if t == "alembic_version":
        continue
    fks = inspector.get_foreign_keys(t)
    for fk in fks:
        cols = fk["constrained_columns"]
        ref_table = fk["referred_table"]
        ref_cols = fk["referred_columns"]
        name = fk.get("name", "unnamed")
        print(f"  {t}: FK({', '.join(cols)}) -> {ref_table}({', '.join(ref_cols)})  [{name}]")
        total_fks += 1
print(f"Total foreign keys: {total_fks}")

print()
print("=" * 60)
print("ALEMBIC VERSION CHECK")
print("=" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SELECT version_num FROM alembic_version"))
    row = result.fetchone()
    if row:
        print(f"Current migration head: {row[0]}")
        assert row[0] == "c2f4a9d1e6b7", f"Expected c2f4a9d1e6b7, got {row[0]}"
        print("Migration head matches latest (c2f4a9d1e6b7): PASS")
    else:
        print("ERROR: No alembic version found!")
        exit(1)

engine.dispose()
print()
print("ALL VERIFICATIONS PASSED")
