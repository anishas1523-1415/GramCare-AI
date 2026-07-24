"""FHIR R4-*shaped* export of a patient's Family Health Wallet.

*** SCOPE — read this before extending or describing this feature ***
This module produces FHIR-*shaped* JSON: a `Bundle` of correctly-structured
FHIR R4 resources (Patient, AllergyIntolerance, MedicationStatement,
DiagnosticReport, Immunization, Observation) built on demand from
GramCare's own EHRRecord rows, so that a receiving hospital/EHR system can
parse a patient's exported history into resource shapes it already
understands (interoperability export).

It is explicitly NOT:
  - A FHIR server. There is no `/Patient?...` search API, no resource
    versioning/history, no persisted FHIR resources — everything here is
    generated fresh from EHRRecord/User/FamilyProfile each time the export
    endpoint is called, then thrown away.
  - HL7v2 / MLLP messaging integration.
  - A live, bidirectional sync with an external EHR. This is a one-shot,
    pull-based export a clinician/patient downloads — not a subscription,
    webhook, or push channel.
  - SMART-on-FHIR authenticated. Access control is GramCare's own JWT auth
    (see modules/ehr_sync/router.py's `export_fhir_bundle` endpoint), not
    an OAuth2/SMART "app launch" flow a real FHIR server would require.

Every resource below is deliberately simple: one resource per EHRRecord row,
carrying GramCare's existing human-readable `content`/`title` as the
clinical detail (`.text`, `valueString`, notes) rather than fully coded
elements — GramCare does not have SNOMED/LOINC/RxNorm-coded clinical data
to draw on, only free text and the loosely-structured `payload` JSON already
stored on EHRRecord. A real hospital EHR ingesting this should treat coded
fields as absent, not assume codes were dropped.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Union

import models

# The subject of an export is either the account owner (models.User) or one
# of their family members (models.FamilyProfile) — whichever the caller
# selected via ?family_profile_id=.
SubjectType = Union[models.User, models.FamilyProfile]

# Only these record_types get a purpose-built FHIR resource; anything else
# (including future/unknown record_types) safely falls back to a generic
# Observation with the content as valueString, per the task's scope.
_RECORD_TYPE_RESOURCE = {
    "prescription": "MedicationStatement",
    "lab_report": "DiagnosticReport",
    "vaccination": "Immunization",
}


def _patient_resource_id(subject: SubjectType) -> str:
    """A stable id for the Patient resource, distinguishing the account
    owner from a family member so re-running the export produces the same
    id (useful if a receiving system wants to de-dupe re-imports)."""
    if isinstance(subject, models.FamilyProfile):
        return f"family-{subject.id}"
    return f"user-{subject.id}"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _gender_code(gender: Optional[str]) -> Optional[str]:
    """Map GramCare's free-text gender field to FHIR's fixed
    AdministrativeGender value set (male | female | other | unknown)."""
    if not gender or not gender.strip():
        return None
    g = gender.strip().lower()
    if g in ("m", "male"):
        return "male"
    if g in ("f", "female"):
        return "female"
    return "other"


def _approx_birth_date(age: Optional[int]) -> Optional[str]:
    """GramCare only ever stores an integer `age`, never a real date of
    birth — this derives an APPROXIMATE calendar year from age and today's
    date, pinned to Jan 1. It is NOT the patient's true birthDate, just
    (current year - age); a FHIR consumer should treat it as low-precision
    (+/- 1 year) demographic context only, never a legal DOB.
    """
    if age is None:
        return None
    year = date.today().year - int(age)
    return f"{year}-01-01"


def _build_patient_resource(subject: SubjectType, patient_id: str) -> Dict[str, Any]:
    is_family_member = isinstance(subject, models.FamilyProfile)

    resource: Dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"text": subject.full_name or "Unknown"}],
    }

    gender_code = _gender_code(getattr(subject, "gender", None))
    if gender_code:
        resource["gender"] = gender_code

    # NOTE: models.User (the account owner) has no `age`/date-of-birth
    # column at all today — only models.FamilyProfile carries `age`. So a
    # self-export (subject is the User) never gets a birthDate here; it's
    # omitted rather than guessed at.
    if is_family_member:
        birth_date = _approx_birth_date(getattr(subject, "age", None))
        if birth_date:
            resource["birthDate"] = birth_date

    blood_group = getattr(subject, "blood_group", None)
    if blood_group and blood_group.strip():
        # Not a registered/published FHIR extension — a placeholder URL
        # documenting intent for a receiving system that cares to look, in
        # lieu of GramCare owning a real namespace to publish one under.
        resource["extension"] = [{
            "url": "http://gramcare.example.org/fhir/StructureDefinition/blood-group",
            "valueString": blood_group.strip(),
        }]

    return resource


def _build_allergy_resources(subject: SubjectType, patient_id: str) -> List[Dict[str, Any]]:
    """One simple AllergyIntolerance per comma-split substance in the
    free-text `allergies` field, present on both User and FamilyProfile."""
    allergies_text = getattr(subject, "allergies", None)
    if not allergies_text or not allergies_text.strip():
        return []

    substances = [s.strip() for s in allergies_text.split(",") if s.strip()]
    resources = []
    for i, substance in enumerate(substances):
        resources.append({
            "resourceType": "AllergyIntolerance",
            "id": f"{patient_id}-allergy-{i}",
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                    "code": "active",
                }],
            },
            "code": {"text": substance},
            "patient": {"reference": f"Patient/{patient_id}"},
        })
    return resources


def _build_record_resource(record: "models.EHRRecord", patient_id: str) -> Dict[str, Any]:
    """Maps one EHRRecord row to the appropriate FHIR resource:
    prescription -> MedicationStatement, lab_report -> DiagnosticReport,
    vaccination -> Immunization, everything else (triage_log/scan/note/
    anything unrecognized) -> a generic Observation with valueString.
    """
    resource_type = _RECORD_TYPE_RESOURCE.get(record.record_type, "Observation")
    resource_id = f"record-{record.id}"
    effective = _iso(record.record_date) or _iso(record.created_at)
    subject_ref = {"reference": f"Patient/{patient_id}"}

    if resource_type == "MedicationStatement":
        resource: Dict[str, Any] = {
            "resourceType": "MedicationStatement",
            "id": resource_id,
            # "unknown" rather than active/completed: a wallet entry doesn't
            # reliably tell us whether the course is still being taken.
            "status": "unknown",
            "subject": subject_ref,
            "medicationCodeableConcept": {"text": record.title or "Prescription"},
            "note": [{"text": record.content}],
        }
        if effective:
            resource["effectiveDateTime"] = effective
            resource["dateAsserted"] = effective
        if record.doctor_name:
            resource["informationSource"] = {"display": record.doctor_name}
        medicines = (record.payload or {}).get("medicines") if isinstance(record.payload, dict) else None
        if medicines:
            resource["dosage"] = [
                {
                    "text": " ".join(
                        str(m.get(k, "")) for k in ("name", "dosage", "frequency", "duration")
                    ).strip()
                }
                for m in medicines
                if isinstance(m, dict)
            ]
        return resource

    if resource_type == "DiagnosticReport":
        resource = {
            "resourceType": "DiagnosticReport",
            "id": resource_id,
            "status": "final",
            "subject": subject_ref,
            "code": {"text": record.title or "Lab Report"},
            "conclusion": record.content,
        }
        if effective:
            resource["effectiveDateTime"] = effective
        if record.doctor_name:
            resource["performer"] = [{"display": record.doctor_name}]
        return resource

    if resource_type == "Immunization":
        resource = {
            "resourceType": "Immunization",
            "id": resource_id,
            "status": "completed",
            "patient": subject_ref,
            "vaccineCode": {"text": record.title or "Vaccination"},
            "note": [{"text": record.content}],
        }
        # occurrence[x] is required (1..1) by the FHIR R4 spec.
        if effective:
            resource["occurrenceDateTime"] = effective
        else:
            resource["occurrenceString"] = "unknown"
        return resource

    # Generic fallback: triage_log / scan / note / any future record_type.
    resource = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "subject": subject_ref,
        "code": {"text": record.title or record.record_type or "Health Record"},
        "valueString": record.content,
    }
    if effective:
        resource["effectiveDateTime"] = effective
    if record.doctor_name:
        resource["performer"] = [{"display": record.doctor_name}]
    return resource


def build_fhir_bundle(subject: SubjectType, ehr_records: List["models.EHRRecord"]) -> Dict[str, Any]:
    """Builds a FHIR R4 `Bundle` (type "collection") for `subject` (a
    models.User or models.FamilyProfile) containing one Patient resource,
    one AllergyIntolerance per allergy substring, and one mapped resource
    per entry in `ehr_records`. See the module docstring for exactly what
    "FHIR-shaped" does and does not mean here.
    """
    patient_id = _patient_resource_id(subject)
    patient_resource = _build_patient_resource(subject, patient_id)

    entries: List[Dict[str, Any]] = [
        {"fullUrl": f"urn:uuid:{patient_id}", "resource": patient_resource},
    ]

    for allergy in _build_allergy_resources(subject, patient_id):
        entries.append({"fullUrl": f"urn:uuid:{allergy['id']}", "resource": allergy})

    for record in ehr_records:
        resource = _build_record_resource(record, patient_id)
        entries.append({"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource})

    return {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": entries,
    }
