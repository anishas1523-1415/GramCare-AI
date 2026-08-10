"""The alembic chain must build a working schema from an empty database.

Replaces the old test_triage.py, which accepted both HTTP 200 and HTTP 500
as passing and therefore verified nothing.
"""
import os
import subprocess
import sys
import tempfile


def test_alembic_upgrade_head_from_scratch():
    service_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{tmp}/migration_test.db"
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=service_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr

        # Spot-check that the Phase 1 tables exist
        import sqlite3
        conn = sqlite3.connect(f"{tmp}/migration_test.db")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for expected in (
            "users", "family_profiles", "doctor_profiles", "availability_slots",
            "payments", "pharmacies", "hospitals", "ehr_records",
            "pharmacy_inventory", "triage_logs", "appointments", "prescriptions",
        ):
            assert expected in tables, f"missing table: {expected}"
