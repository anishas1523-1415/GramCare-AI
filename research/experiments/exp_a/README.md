# Experiment A — offline synchronisation reliability

Start with [results.md](../../../docs/research/experiments/exp_a/results.md).

| Phase | Artefact |
|---|---|
| 1 — implementation audit | `docs/research/experiments/exp_a/implementation_audit.md` |
| 2 — protocol | `docs/research/experiments/exp_a/experiment_protocol.md` |
| 3 — scenario harness | `sync_reliability.py` → `results/exp_a_raw.csv` (46 scenarios) |
| 4 — metrics harness | `sync_metrics.py` → `results/exp_a_metrics.csv` (19 metrics) |
| results | `docs/research/experiments/exp_a/results.md` |

## Run

```powershell
docker run -d --name expa_postgres -e POSTGRES_PASSWORD=expa_synthetic_only -e POSTGRES_USER=expa -e POSTGRES_DB=expa_sync -p 5434:5432 postgres:15-alpine
```

```powershell
cd backend/python_service
$env:EXPA_DATABASE_URL = "postgresql://expa:expa_synthetic_only@localhost:5434/expa_sync"; .venv\Scripts\python.exe ..\..\research\experiments\exp_a\sync_reliability.py
```

```powershell
$env:EXPA_DATABASE_URL = "postgresql://expa:expa_synthetic_only@localhost:5434/expa_metrics"; .venv\Scripts\python.exe ..\..\research\experiments\exp_a\sync_metrics.py
```

Both scripts refuse to run on SQLite and refuse any managed-host URL. They
rebuild the schema, seed their own synthetic patients, and blank every external
credential before importing the app.

## Headline

Duplicate insertion rate **0/600**. Recovery from an interrupted sync
**30/30**. Ten-way concurrent delivery **30/30** correct with **0/300** server
errors. The idempotency mechanism does what it claims.

Then three failures:

- **maximum drainable queue depth is exactly 100 records.** At 101, nothing
  persists and the queue can never drain.
- **one record for a deleted family profile blocks all 9 valid records** behind
  it.
- **a `client_uuid` collision across two patients silently destroys the second
  patient's record — 30/30, rate 1.0000.**

## Two things worth knowing before reading the numbers

**An HTTP 200 is never a pass.** Every verdict is computed from an integrity
ledger read back from the database: submitted, persisted, unique, duplicates,
missing, unexpected, overwritten, cross-tenant.

**Each group runs a positive control first.** If the control fails, every result
in that group is reported INCONCLUSIVE rather than PASSED. All 7 controls passed
on the reported run.

The first run of the scenario harness produced 20 spurious failures because the
fixture `client_uuid` values were 7 characters and `EHRSyncItem` requires 8. That
was a harness defect, not a product defect; the generator now asserts the length.
