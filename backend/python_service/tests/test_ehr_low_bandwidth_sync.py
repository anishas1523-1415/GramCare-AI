"""Low-bandwidth EHR sync optimizations for GET /ehr/patient/{patient_id}:

- `since`: incremental sync — only records created after a given timestamp,
  so a mobile client that already has everything up to its last successful
  sync doesn't have to re-download the whole wallet every time.
- `skip`/`limit`: pagination, which this endpoint already had before this
  change (default 100, max 200) — these tests confirm it still behaves as
  documented alongside the new `since` filter, not that it was newly added.

(Response gzip compression, the other low-bandwidth change in this batch,
is transport-level middleware behavior — not meaningfully testable through
TestClient, which talks to the ASGI app in-process without real HTTP
encoding, so it isn't covered here.)
"""
from tests.conftest import auth, _register_and_login


def _create_note(client, token, content):
    res = client.post(
        "/api/v1/ehr/record",
        headers=auth(token),
        json={"record_type": "note", "title": content, "content": content},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_since_filters_to_records_created_after_the_given_timestamp(client):
    token = _register_and_login(client, "sync_patient1", "PATIENT")
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    patient_id = me["id"]

    first = _create_note(client, token, "First record")
    second = _create_note(client, token, "Second record")

    # No `since` -> both records present.
    all_res = client.get(f"/api/v1/ehr/patient/{patient_id}", headers=auth(token))
    assert all_res.status_code == 200, all_res.text
    all_ids = {r["id"] for r in all_res.json()}
    assert {first["id"], second["id"]}.issubset(all_ids)

    # `since` = first record's created_at -> only strictly-later records
    # (the second one) come back; the first is excluded (not "since" itself).
    since_res = client.get(
        f"/api/v1/ehr/patient/{patient_id}",
        headers=auth(token),
        params={"since": first["created_at"]},
    )
    assert since_res.status_code == 200, since_res.text
    since_ids = {r["id"] for r in since_res.json()}
    assert second["id"] in since_ids
    assert first["id"] not in since_ids


def test_pagination_limit_and_skip(client):
    token = _register_and_login(client, "sync_patient2", "PATIENT")
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    patient_id = me["id"]

    created = [_create_note(client, token, f"Record {i}") for i in range(3)]
    created_ids = {r["id"] for r in created}

    page1 = client.get(
        f"/api/v1/ehr/patient/{patient_id}",
        headers=auth(token),
        params={"limit": 2, "skip": 0},
    )
    assert page1.status_code == 200, page1.text
    assert len(page1.json()) == 2

    page2 = client.get(
        f"/api/v1/ehr/patient/{patient_id}",
        headers=auth(token),
        params={"limit": 2, "skip": 2},
    )
    assert page2.status_code == 200, page2.text
    page2_records = page2.json()
    assert len(page2_records) == 1

    # Together, the two pages cover exactly the 3 records created (records
    # are ordered by record_date desc, so pages don't overlap).
    seen_ids = {r["id"] for r in page1.json()} | {r["id"] for r in page2_records}
    assert seen_ids == created_ids

    # `limit` is capped at 200 by the endpoint's own Query(..., le=200).
    too_big = client.get(
        f"/api/v1/ehr/patient/{patient_id}",
        headers=auth(token),
        params={"limit": 500},
    )
    assert too_big.status_code == 422
