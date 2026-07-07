"""Phase 5 contract tests: pharmacy registration, stock lifecycle,
fulfillment decrement, expiry alerts, geo search + substitutes."""
from datetime import date, timedelta

from tests.conftest import auth, _register_and_login


def _setup_pharmacy(client, username="p5_pharma"):
    token = _register_and_login(client, username, "PHARMACIST")
    reg = client.post("/api/v1/pharmacy/register", headers=auth(token), json={
        # Unique per owner: several tests register shops, and search
        # assertions must be able to pick out the right one.
        "name": f"Grama Medicals {username}",
        "address": "Main Road, Sivaganga",
        "lat": 9.8433, "lng": 78.4809,
        "phone": "+91-9000000001",
    })
    assert reg.status_code == 200, reg.text
    return token, reg.json()["id"]


def test_stock_requires_registration_first(client):
    token = _register_and_login(client, "p5_unregistered", "PHARMACIST")
    res = client.get("/api/v1/pharmacy/stock", headers=auth(token))
    assert res.status_code == 409  # register first


def test_inventory_lifecycle(client):
    token, _ = _setup_pharmacy(client)

    created = client.post("/api/v1/pharmacy/items", headers=auth(token), json={
        "medicine_name": "Paracetamol 500mg",
        "generic_group": "paracetamol-500",
        "stock_count": 40,
        "price": 20.0,
        "expiry_date": str(date.today() + timedelta(days=30)),
    })
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert created.json()["status"] == "Low"  # 40 < 50

    # Shipment +20
    assert client.post(f"/api/v1/pharmacy/update_stock/{item_id}?quantity_added=20",
                       headers=auth(token)).status_code == 200
    # Tap-to-decrement (sold 1)
    assert client.post(f"/api/v1/pharmacy/decrement/{item_id}",
                       headers=auth(token)).status_code == 200
    # Absolute end-of-day count
    assert client.post(f"/api/v1/pharmacy/set_stock/{item_id}?count=100",
                       headers=auth(token)).status_code == 200

    stock = client.get("/api/v1/pharmacy/stock", headers=auth(token)).json()
    me_item = next(i for i in stock if i["id"] == item_id)
    assert me_item["stock_count"] == 100
    assert me_item["status"] == "Optimal"

    # Expiry alert appears (expires in 30 days, window 90)
    expiring = client.get("/api/v1/pharmacy/expiring?days=90", headers=auth(token)).json()
    assert any(i["id"] == item_id for i in expiring)
    assert all("days_left" in i for i in expiring)


def test_patient_cannot_touch_inventory(client, patient_token):
    assert client.get("/api/v1/pharmacy/stock", headers=auth(patient_token)).status_code == 403
    assert client.post("/api/v1/pharmacy/items", headers=auth(patient_token), json={
        "medicine_name": "X", "stock_count": 1,
    }).status_code == 403


def test_fulfillment_decrements_stock(client, doctor_token, patient_token):
    pharma_token, pharmacy_id = _setup_pharmacy(client, "p5_pharma2")
    client.post("/api/v1/pharmacy/items", headers=auth(pharma_token), json={
        "medicine_name": "Amoxicillin 250mg", "stock_count": 5,
    })

    me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
    rx = client.post("/api/v1/ehr/issue_prescription", headers=auth(doctor_token), json={
        "patient_id": me["id"],
        "medicines": [{"name": "Amoxicillin 250mg", "dosage": "250mg",
                       "frequency": "1-1-1", "duration": "5 days"}],
        "diagnosis": "Bacterial infection",
    })
    assert rx.status_code == 200, rx.text

    queue = client.get("/api/v1/pharmacy/queue", headers=auth(pharma_token)).json()
    assert any(q["id"] == rx.json()["id"] for q in queue)

    fulfilled = client.put(f"/api/v1/pharmacy/fulfill/{rx.json()['id']}",
                           headers=auth(pharma_token))
    assert fulfilled.status_code == 200, fulfilled.text
    assert "Amoxicillin 250mg" in fulfilled.json()["stock_decremented"]

    stock = client.get("/api/v1/pharmacy/stock", headers=auth(pharma_token)).json()
    amox = next(i for i in stock if i["medicine_name"] == "Amoxicillin 250mg")
    assert amox["stock_count"] == 4  # decremented by 1


def test_search_availability_and_substitutes(client, patient_token):
    pharma_token, _ = _setup_pharmacy(client, "p5_pharma3")
    r1 = client.post("/api/v1/pharmacy/items", headers=auth(pharma_token), json={
        "medicine_name": "Dolo 650", "generic_group": "para-650",
        "stock_count": 50, "price": 32.0,
    })
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/pharmacy/items", headers=auth(pharma_token), json={
        "medicine_name": "Calpol 650", "generic_group": "para-650",
        "stock_count": 0, "price": 30.0,
    })
    assert r2.status_code == 201, r2.text

    # Available medicine → green
    res = client.get("/api/v1/pharmacy/search", headers=auth(patient_token),
                     params={"medicine": "Dolo", "lat": 9.85, "lng": 78.48})
    assert res.status_code == 200, res.text
    hit = next(r for r in res.json() if r["pharmacy_name"] == "Grama Medicals p5_pharma3")
    assert hit["available"] is True
    assert hit["distance_km"] is not None

    # Unavailable medicine → red + in-stock generic substitute suggested
    res2 = client.get("/api/v1/pharmacy/search", headers=auth(patient_token),
                      params={"medicine": "Calpol"})
    hits = [r for r in res2.json() if r["pharmacy_name"] == "Grama Medicals p5_pharma3"]
    assert hits and hits[0]["available"] is False
    assert "Dolo 650" in hits[0]["substitutes"]

    # Network-wide substitutes endpoint
    subs = client.get("/api/v1/pharmacy/substitutes", headers=auth(patient_token),
                      params={"medicine": "Calpol 650"}).json()
    assert any(s["name"] == "Dolo 650" for s in subs)


def test_batch_recall_alerts_reach_both_pharmacist_and_patient(client):
    """Planning doc: recalls must reach "பார்மசிஸ்ட்களும் யூசர்களும்" —
    pharmacists AND patients, not pharmacists alone."""
    pharma_token, pharmacy_id = _setup_pharmacy(client, "p5_recall_pharma")
    client.post("/api/v1/pharmacy/items", headers=auth(pharma_token), json={
        "medicine_name": "Ranitidine 150mg",
        "stock_count": 20,
        "batch_number": "BATCH-XYZ-1",
    })

    admin_token = _register_and_login(client, "p5_recall_admin", "ADMIN")
    issued = client.post("/api/v1/pharmacy/recalls", headers=auth(admin_token), json={
        "medicine_name": "Ranitidine 150mg",
        "batch_number": "BATCH-XYZ-1",
        "reason": "Impurity detected above safety threshold",
    })
    assert issued.status_code == 201, issued.text

    # Reaches the pharmacist holding that exact batch
    pharma_recalls = client.get("/api/v1/pharmacy/recalls/mine", headers=auth(pharma_token)).json()
    assert any(r["medicine_name"] == "Ranitidine 150mg" for r in pharma_recalls)

    # Reaches a patient who was prescribed that medicine (name-level match)
    patient_token = _register_and_login(client, "p5_recall_patient", "PATIENT")
    me = client.get("/api/v1/auth/me", headers=auth(patient_token)).json()
    doctor_token = _register_and_login(client, "p5_recall_doctor", "DOCTOR")
    rx = client.post("/api/v1/ehr/issue_prescription", headers=auth(doctor_token), json={
        "patient_id": me["id"],
        "medicines": [{"name": "Ranitidine 150mg", "dosage": "150mg",
                       "frequency": "1-0-1", "duration": "10 days"}],
        "diagnosis": "Acid reflux",
    })
    assert rx.status_code == 200, rx.text

    affecting_me = client.get("/api/v1/pharmacy/recalls/affecting-me", headers=auth(patient_token)).json()
    assert any(r["medicine_name"] == "Ranitidine 150mg" for r in affecting_me)

    # A patient never prescribed it sees nothing
    other_patient = _register_and_login(client, "p5_recall_unaffected", "PATIENT")
    unaffected = client.get("/api/v1/pharmacy/recalls/affecting-me", headers=auth(other_patient)).json()
    assert unaffected == []


def test_medicine_info_assistant(client):
    """Medicine Information Assistant — provider-agnostic assertions since
    a dev environment's real (non-Gemini) AI keys may legitimately answer
    this instead of the mock fallback (same philosophy as
    test_triage_mock_persists_log)."""
    token = _register_and_login(client, "p5_info_patient", "PATIENT")
    res = client.get("/api/v1/pharmacy/medicine-info", headers=auth(token),
                     params={"medicine": "Paracetamol 500mg"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["medicine_name"] == "Paracetamol 500mg"
    assert body["purpose"]
    assert body["dosage_guidance"]
    assert body["generated_by"]
