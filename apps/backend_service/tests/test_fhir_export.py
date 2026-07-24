"""FHIR-R4-*shaped* Family Health Wallet export (GET /ehr/fhir-export).

Scope reminder (see core/fhir_export.py's module docstring for the full
version): this endpoint returns correctly-structured FHIR R4 resources in a
`Bundle`, generated on the fly from EHRRecord/User/FamilyProfile rows. It is
NOT a FHIR server, does not do SMART-on-FHIR auth, and does not sync to any
external system — these tests only assert on the shape and access control
of that export, not on any broader FHIR-server behavior.
"""
from tests.conftest import auth, _register_and_login


def _create_record(client, token, record_type, title, content, family_profile_id=None):
    res = client.post(
        "/api/v1/ehr/record",
        headers=auth(token),
        json={
            "record_type": record_type,
            "title": title,
            "content": content,
            "family_profile_id": family_profile_id,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_bundle_shape_and_resource_mapping(client):
    token = _register_and_login(client, "fhir_patient1", "PATIENT")

    # Give the passport some blood group + two allergies so the Patient/
    # AllergyIntolerance mapping has real data to work with.
    client.put(
        "/api/v1/passport/me",
        headers=auth(token),
        json={"blood_group": "O+", "allergies": "Penicillin, Peanuts", "chronic_conditions": "Asthma"},
    )

    _create_record(client, token, "prescription", "Fever", "Paracetamol 500mg twice daily")
    _create_record(client, token, "lab_report", "CBC", "Hemoglobin 13.2 g/dL, normal")
    _create_record(client, token, "vaccination", "Tetanus", "Tetanus booster administered")
    _create_record(client, token, "note", "Follow-up", "Patient reports feeling better")

    res = client.get("/api/v1/ehr/fhir-export", headers=auth(token))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/json")
    assert 'filename="gramcare_health_records_fhir.json"' in res.headers["content-disposition"]

    bundle = res.json()  # must be valid JSON
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert isinstance(bundle["entry"], list)

    resources = [e["resource"] for e in bundle["entry"]]
    by_type = {}
    for r in resources:
        by_type.setdefault(r["resourceType"], []).append(r)

    # Exactly one Patient entry.
    assert len(by_type.get("Patient", [])) == 1
    patient = by_type["Patient"][0]
    assert patient["name"][0]["text"] == "Fhir_Patient1"

    # One AllergyIntolerance per comma-split allergy substring.
    assert len(by_type.get("AllergyIntolerance", [])) == 2
    allergy_texts = {a["code"]["text"] for a in by_type["AllergyIntolerance"]}
    assert allergy_texts == {"Penicillin", "Peanuts"}

    # One mapped resource per EHRRecord fixture created above.
    assert len(by_type.get("MedicationStatement", [])) == 1
    assert by_type["MedicationStatement"][0]["medicationCodeableConcept"]["text"] == "Fever"

    assert len(by_type.get("DiagnosticReport", [])) == 1
    assert by_type["DiagnosticReport"][0]["conclusion"] == "Hemoglobin 13.2 g/dL, normal"

    assert len(by_type.get("Immunization", [])) == 1
    assert by_type["Immunization"][0]["vaccineCode"]["text"] == "Tetanus"

    # "note" has no dedicated FHIR resource -> generic Observation fallback.
    assert len(by_type.get("Observation", [])) == 1
    assert by_type["Observation"][0]["valueString"] == "Patient reports feeling better"

    # Every non-Patient resource references the Patient back.
    for r in resources:
        if r["resourceType"] == "Patient":
            continue
        ref = r.get("subject", r.get("patient"))
        assert ref["reference"] == f"Patient/{patient['id']}"


def test_family_profile_scoped_export_uses_family_member_as_patient(client):
    token = _register_and_login(client, "fhir_patient2", "PATIENT")

    profile_res = client.post(
        "/api/v1/family",
        headers=auth(token),
        json={
            "full_name": "Little Kumar",
            "relation": "Son",
            "age": 8,
            "gender": "Male",
            "allergies": "Amoxicillin",
        },
    )
    assert profile_res.status_code == 201, profile_res.text
    family_profile_id = profile_res.json()["id"]

    # A record for the account owner (should NOT show up in the scoped export).
    _create_record(client, token, "note", "Adult note", "This belongs to the account owner")
    # A record for the family member (SHOULD show up).
    _create_record(
        client, token, "vaccination", "Polio", "Polio dose 1",
        family_profile_id=family_profile_id,
    )

    res = client.get(
        "/api/v1/ehr/fhir-export",
        headers=auth(token),
        params={"family_profile_id": family_profile_id},
    )
    assert res.status_code == 200, res.text
    bundle = res.json()

    patient = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    assert patient["name"][0]["text"] == "Little Kumar"
    assert patient["gender"] == "male"
    assert patient["birthDate"] is not None  # derived from FamilyProfile.age

    allergy_entries = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance"]
    assert len(allergy_entries) == 1
    assert allergy_entries[0]["code"]["text"] == "Amoxicillin"

    immunizations = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Immunization"]
    assert len(immunizations) == 1
    assert immunizations[0]["vaccineCode"]["text"] == "Polio"

    # The account owner's own "note" record must not leak into the
    # family-member-scoped export.
    observations = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"]
    assert len(observations) == 0


def test_non_patient_role_is_rejected(client, doctor_token):
    res = client.get("/api/v1/ehr/fhir-export", headers=auth(doctor_token))
    assert res.status_code == 403


def test_cannot_export_another_patients_family_profile(client):
    owner_token = _register_and_login(client, "fhir_owner", "PATIENT")
    intruder_token = _register_and_login(client, "fhir_intruder", "PATIENT")

    profile_res = client.post(
        "/api/v1/family",
        headers=auth(owner_token),
        json={"full_name": "Owner's Kid", "relation": "Daughter", "age": 5, "gender": "Female"},
    )
    assert profile_res.status_code == 201, profile_res.text
    family_profile_id = profile_res.json()["id"]

    res = client.get(
        "/api/v1/ehr/fhir-export",
        headers=auth(intruder_token),
        params={"family_profile_id": family_profile_id},
    )
    assert res.status_code == 403


def test_requires_authentication(client):
    res = client.get("/api/v1/ehr/fhir-export")
    assert res.status_code == 401
