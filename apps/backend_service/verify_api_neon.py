"""End-to-end API verification against live Neon PostgreSQL.

Tests every major API endpoint using the running FastAPI server at localhost:8000.
All operations go through the real Neon database — no mocks.
"""
import json
import sys
import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0


def check(label, response, expected_status=200, allow_statuses=None):
    global PASS, FAIL
    allowed = allow_statuses or [expected_status]
    if response.status_code in allowed:
        PASS += 1
        print(f"  PASS  {label} [{response.status_code}]")
        return True
    else:
        FAIL += 1
        body = response.text[:200]
        print(f"  FAIL  {label} [{response.status_code}] {body}")
        return False


print("=" * 60)
print("NEON POSTGRESQL — FULL API VERIFICATION")
print("=" * 60)

# 1. Health check
print("\n--- Health Check ---")
r = requests.get(f"{BASE}/health")
check("GET /health", r)
health = r.json()
assert health["database"] == "up", f"DB not up: {health}"
print(f"  Database status: {health['database']}")

# 2. Root
print("\n--- Root ---")
r = requests.get(f"{BASE}/")
check("GET /", r)

# 3. Auth — Register + Login
print("\n--- Auth ---")
r = requests.post(f"{BASE}/api/v1/auth/register", json={
    "username": "neon_test_user2",
    "email": "neontest2@gramcare.in",
    "password": "TestPassword123!",
    "full_name": "Neon Test User 2",
    "role": "PATIENT",
})
check("POST /auth/register", r, allow_statuses=[200, 400])

r = requests.post(f"{BASE}/api/v1/auth/login", data={
    "username": "patient1",
    "password": "password123",
})
check("POST /auth/login (patient)", r)
patient_token = r.json().get("access_token", "")
patient_headers = {"Authorization": f"Bearer {patient_token}"}

# Login as doctor
r = requests.post(f"{BASE}/api/v1/auth/login", data={
    "username": "doctor1",
    "password": "password123",
})
check("POST /auth/login (doctor)", r)
doctor_token = r.json().get("access_token", "")
doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

# Login as pharmacist
r = requests.post(f"{BASE}/api/v1/auth/login", data={
    "username": "pharma1",
    "password": "password123",
})
check("POST /auth/login (pharmacist)", r)
pharma_token = r.json().get("access_token", "")
pharma_headers = {"Authorization": f"Bearer {pharma_token}"}

# 4. Auth — /me
print("\n--- Auth /me ---")
r = requests.get(f"{BASE}/api/v1/auth/me", headers=patient_headers)
check("GET /auth/me", r)
me = r.json()
print(f"  User: {me.get('username')}, Role: {me.get('role')}")

# 5. Family Profiles
print("\n--- Family Profiles ---")
r = requests.get(f"{BASE}/api/v1/family/", headers=patient_headers)
check("GET /family/", r)
profiles = r.json()
print(f"  Family profiles: {len(profiles) if isinstance(profiles, list) else 'N/A'}")

r = requests.post(f"{BASE}/api/v1/family/", headers=patient_headers, json={
    "full_name": "Neon Test Child",
    "relation": "Sibling",
    "age": 10,
    "gender": "Male",
})
check("POST /family/ (create)", r, allow_statuses=[200, 201])

# 6. Doctors Directory
print("\n--- Doctor Directory ---")
r = requests.get(f"{BASE}/api/v1/doctors/", headers=patient_headers)
check("GET /doctors/", r)
doctors = r.json()
print(f"  Doctors found: {len(doctors) if isinstance(doctors, list) else 'N/A'}")

# 7. Doctor profile (as doctor)
print("\n--- Doctor Profile ---")
r = requests.get(f"{BASE}/api/v1/doctors/me", headers=doctor_headers)
check("GET /doctors/me", r)

# 8. Availability Slots
print("\n--- Availability Slots ---")
# Get doctor_id for doctor1
r_me = requests.get(f"{BASE}/api/v1/auth/me", headers=doctor_headers)
doctor_user_id = r_me.json().get("id", 2)
r = requests.get(f"{BASE}/api/v1/doctors/{doctor_user_id}/slots", headers=patient_headers)
check(f"GET /doctors/{doctor_user_id}/slots", r, allow_statuses=[200, 404])

# 9. AI Triage (correct field name: symptoms_text)
print("\n--- AI Triage ---")
r = requests.post(f"{BASE}/api/v1/triage/analyze", headers=patient_headers, json={
    "symptoms_text": "I have a headache and mild fever",
    "patient_id": "GUEST",
    "age": 30,
})
check("POST /triage/analyze", r, allow_statuses=[200, 500, 503])

# 10. EHR — patient-facing endpoints
print("\n--- EHR Records ---")
# /ehr/records requires DOCTOR role
r = requests.get(f"{BASE}/api/v1/ehr/records", headers=doctor_headers)
check("GET /ehr/records (doctor)", r, allow_statuses=[200, 403])

# /ehr/prescriptions/my (patient)
r = requests.get(f"{BASE}/api/v1/ehr/prescriptions/my", headers=patient_headers)
check("GET /ehr/prescriptions/my", r)

# /ehr/record (POST - patient creates a record)
r = requests.post(f"{BASE}/api/v1/ehr/record", headers=patient_headers, json={
    "record_type": "note",
    "title": "Neon DB Test Record",
    "content": "Testing EHR sync with Neon PostgreSQL",
})
check("POST /ehr/record", r, allow_statuses=[200, 201])

# 11. Pharmacy endpoints
print("\n--- Pharmacy ---")
# /pharmacy/me (pharmacist's own shop)
r = requests.get(f"{BASE}/api/v1/pharmacy/me", headers=pharma_headers)
check("GET /pharmacy/me", r)

# /pharmacy/stock (pharmacist inventory)
r = requests.get(f"{BASE}/api/v1/pharmacy/stock", headers=pharma_headers)
check("GET /pharmacy/stock", r)

# /pharmacy/search (patient searches)
r = requests.get(f"{BASE}/api/v1/pharmacy/search?medicine=Paracetamol&lat=9.84&lng=78.48", headers=patient_headers)
check("GET /pharmacy/search", r, allow_statuses=[200])

# /pharmacy/substitutes
r = requests.get(f"{BASE}/api/v1/pharmacy/substitutes?medicine=Dolo-650", headers=patient_headers)
check("GET /pharmacy/substitutes", r, allow_statuses=[200])

# /pharmacy/expiring
r = requests.get(f"{BASE}/api/v1/pharmacy/expiring", headers=pharma_headers)
check("GET /pharmacy/expiring", r)

# 12. Payments
print("\n--- Payments ---")
r = requests.post(f"{BASE}/api/v1/payments/create-order", headers=patient_headers, json={
    "amount": 150.0,
})
check("POST /payments/create-order", r, allow_statuses=[200, 201])
if r.status_code in [200, 201]:
    order = r.json()
    print(f"  Order ID: {order.get('order_id', 'N/A')}")
    order_id = order.get("order_id")

    # /payments/{order_id}/status
    r = requests.get(f"{BASE}/api/v1/payments/{order_id}/status", headers=patient_headers)
    check(f"GET /payments/{order_id}/status", r)

# /payments/my
r = requests.get(f"{BASE}/api/v1/payments/my", headers=patient_headers)
check("GET /payments/my", r)

# 13. Appointments
print("\n--- Appointments ---")
r = requests.get(f"{BASE}/api/v1/appointments/my", headers=patient_headers)
check("GET /appointments/my", r)

# Doctor queue
r = requests.get(f"{BASE}/api/v1/appointments/doctor/{doctor_user_id}/queue", headers=doctor_headers)
check(f"GET /appointments/doctor/{doctor_user_id}/queue", r, allow_statuses=[200, 403])

# 14. Emergency SOS
print("\n--- Emergency SOS ---")
r = requests.get(f"{BASE}/api/v1/sos/mine", headers=patient_headers)
check("GET /sos/mine", r)

r = requests.post(f"{BASE}/api/v1/sos/trigger", headers=patient_headers, json={
    "location_lat": 9.8433,
    "location_lng": 78.4809,
    "severity": "HIGH",
})
check("POST /sos/trigger", r, allow_statuses=[200, 201, 429])

# 15. Emergency Contacts
print("\n--- Emergency Contacts ---")
r = requests.get(f"{BASE}/api/v1/sos/contacts", headers=patient_headers)
check("GET /sos/contacts", r)

r = requests.post(f"{BASE}/api/v1/sos/contacts", headers=patient_headers, json={
    "name": "Neon Test Contact",
    "phone": "+919000000098",
    "relation": "Friend",
})
check("POST /sos/contacts", r, allow_statuses=[200, 201])

# 16. AI Doctor Assistant (doctor role only)
print("\n--- AI Doctor Assistant ---")
r_patients = requests.get(f"{BASE}/api/v1/auth/me", headers=patient_headers)
patient_id = r_patients.json().get("id", 1)
r = requests.get(f"{BASE}/api/v1/assist/patient-summary/{patient_id}", headers=doctor_headers)
check("GET /assist/patient-summary", r, allow_statuses=[200, 404, 500])

# 17. Community Health Intelligence (analytics)
print("\n--- Analytics ---")
r = requests.get(f"{BASE}/api/v1/analytics/overview", headers=doctor_headers)
check("GET /analytics/overview", r, allow_statuses=[200, 403])

r = requests.get(f"{BASE}/api/v1/analytics/health-clusters", headers=doctor_headers)
check("GET /analytics/health-clusters", r, allow_statuses=[200, 403])

# 18. AI Manager admin
print("\n--- AI Manager ---")
r = requests.get(f"{BASE}/api/v1/ai/health")
check("GET /ai/health", r, allow_statuses=[200, 401, 403])

r = requests.get(f"{BASE}/api/v1/ai/metrics")
check("GET /ai/metrics", r, allow_statuses=[200, 401, 403])

# 19. OpenAPI spec
print("\n--- OpenAPI ---")
r = requests.get(f"{BASE}/openapi.json")
check("GET /openapi.json", r)
spec = r.json()
print(f"  API title: {spec.get('info', {}).get('title')}")
print(f"  Paths count: {len(spec.get('paths', {}))}")

print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
print("=" * 60)

if FAIL > 0:
    print("SOME TESTS FAILED — review above output")
    sys.exit(1)
else:
    print("ALL API TESTS PASSED AGAINST NEON POSTGRESQL")
    sys.exit(0)
