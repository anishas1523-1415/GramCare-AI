"""Lab Test catalog — curated reference data backing the planning doc's
"Pre-test preparation instructions" requirement: "இது எந்த டெஸ்ட்டுக்கு
எவ்வளவு நாள் ஃபாஸ்டிங் தேவைன்னு காட்டணும்" (fasting hours before a test,
etc.). Real, commonly used lab tests with genuine prep guidance — not a
placeholder — so search/booking works fully offline-of-any-external-API
today. A production deployment can swap this for a licensed catalog behind
the same `search_tests` / `get_test` signatures.
"""
from typing import List, Optional, TypedDict


class LabTestInfo(TypedDict):
    name: str
    category: str
    prep_instructions: str
    typical_turnaround_hours: int
    sample_type: str


_CATALOG: List[LabTestInfo] = [
    {"name": "Complete Blood Count (CBC)", "category": "Hematology",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 6, "sample_type": "Blood"},
    {"name": "Fasting Blood Sugar (FBS)", "category": "Diabetes",
     "prep_instructions": "Fast for 8-10 hours (water allowed). Take the sample before breakfast.",
     "typical_turnaround_hours": 4, "sample_type": "Blood"},
    {"name": "Postprandial Blood Sugar (PPBS)", "category": "Diabetes",
     "prep_instructions": "Eat a normal meal, then the sample is taken exactly 2 hours later.",
     "typical_turnaround_hours": 4, "sample_type": "Blood"},
    {"name": "HbA1c", "category": "Diabetes",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 24, "sample_type": "Blood"},
    {"name": "Lipid Profile", "category": "Cardiology",
     "prep_instructions": "Fast for 9-12 hours before the test (water allowed).",
     "typical_turnaround_hours": 12, "sample_type": "Blood"},
    {"name": "Liver Function Test (LFT)", "category": "Liver",
     "prep_instructions": "Fast for 8 hours; avoid alcohol for 24 hours before the test.",
     "typical_turnaround_hours": 12, "sample_type": "Blood"},
    {"name": "Kidney Function Test (KFT/RFT)", "category": "Kidney",
     "prep_instructions": "No special preparation; stay well-hydrated.",
     "typical_turnaround_hours": 12, "sample_type": "Blood"},
    {"name": "Thyroid Profile (T3, T4, TSH)", "category": "Endocrine",
     "prep_instructions": "No fasting required; preferably done in the morning.",
     "typical_turnaround_hours": 24, "sample_type": "Blood"},
    {"name": "Urine Routine Examination", "category": "Urology",
     "prep_instructions": "Collect a mid-stream first-morning sample in a clean, dry container.",
     "typical_turnaround_hours": 4, "sample_type": "Urine"},
    {"name": "Widal Test (Typhoid)", "category": "Infectious Disease",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 12, "sample_type": "Blood"},
    {"name": "Dengue NS1/IgG/IgM", "category": "Infectious Disease",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 6, "sample_type": "Blood"},
    {"name": "Malaria Parasite Test", "category": "Infectious Disease",
     "prep_instructions": "No fasting required; best drawn during fever spike.",
     "typical_turnaround_hours": 2, "sample_type": "Blood"},
    {"name": "X-Ray Chest", "category": "Radiology",
     "prep_instructions": "No preparation needed; remove metal objects/jewelry before the scan.",
     "typical_turnaround_hours": 2, "sample_type": "Imaging"},
    {"name": "ECG", "category": "Cardiology",
     "prep_instructions": "No fasting required; avoid caffeine for 1 hour before the test.",
     "typical_turnaround_hours": 1, "sample_type": "Cardiac"},
    {"name": "Vitamin D Test", "category": "Vitamins",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 24, "sample_type": "Blood"},
    {"name": "Vitamin B12 Test", "category": "Vitamins",
     "prep_instructions": "No fasting required.", "typical_turnaround_hours": 24, "sample_type": "Blood"},
    {"name": "Pregnancy Test (Beta-hCG)", "category": "Obstetrics",
     "prep_instructions": "No fasting required; first-morning urine gives the most reliable result.",
     "typical_turnaround_hours": 2, "sample_type": "Urine/Blood"},
    {"name": "COVID-19 RT-PCR", "category": "Infectious Disease",
     "prep_instructions": "Avoid eating, drinking, or smoking for 30 minutes before the swab.",
     "typical_turnaround_hours": 24, "sample_type": "Nasal/Throat Swab"},
]

_BY_NAME = {t["name"].lower(): t for t in _CATALOG}


def search_tests(query: str) -> List[LabTestInfo]:
    q = (query or "").strip().lower()
    if not q:
        return _CATALOG
    return [t for t in _CATALOG if q in t["name"].lower() or q in t["category"].lower()]


def get_test(name: str) -> Optional[LabTestInfo]:
    return _BY_NAME.get((name or "").strip().lower())


def full_catalog() -> List[LabTestInfo]:
    return _CATALOG
