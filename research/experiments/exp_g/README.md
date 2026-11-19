# Experiment G — cross-role, cross-tenant isolation matrix

| File | What it is |
|---|---|
| `isolation_matrix.py` | the harness: seeds two tenants per role, probes 4 axes |
| `verify_ehr_records_scoping.py` | positive-case check for the `/ehr/records` fix |
| `RESULTS.md` | the write-up: method, findings, before/after, threats to validity |
| `results/isolation_matrix_raw.csv` | one row per probe — caller, expectation, status, excerpt |
| `results/isolation_matrix_summary.json` | git SHA, timestamp, per-axis counts |

## Run

```
cd backend/python_service
.venv/Scripts/python.exe ../../research/experiments/exp_g/isolation_matrix.py
.venv/Scripts/python.exe ../../research/experiments/exp_g/verify_ehr_records_scoping.py
```

Both are self-contained: they create a throwaway SQLite database, blank every
external credential, seed their own synthetic accounts, and touch no production
data and no third-party service.

## Why the second script exists

`isolation_matrix.py` only inspects HTTP 200 responses for a leaked canary, so an
endpoint that began returning 500 after a fix would be recorded as "no finding" —
a false pass. `verify_ehr_records_scoping.py` checks the positive case
explicitly: the doctor who *has* a relationship with the patient must still see
the record, an unrelated doctor must get an empty list rather than an error, and
ADMIN must still see everything.
