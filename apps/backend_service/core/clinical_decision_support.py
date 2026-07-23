"""Clinical Decision Support (CDS) — planning doc: beyond the existing
Medicine Interaction Alerts (core/drug_interactions.py), the doctor's
prescription-writing flow gets three more rule-based safety checks:

  a. Allergy cross-check   — patient's stored allergies vs. the medicines
                              being prescribed.
  b. Duplicate-therapy     — a medicine already active from another
                              prescription.
  c. Dosage-sanity flag    — the same medicine prescribed before at a
                              meaningfully different dosage.

Every function here returns a list of `CdsAlert` dicts sharing one shape —
`category` / `severity` / `message` / `explanation` — so the /cds/check
endpoint (modules/cds/router.py) can concatenate them with the (separately
normalized) drug-interaction warnings into one combined alert list. Explainable
AI requirement: `explanation` is the plain-language "why", mirroring the
`explanation` field already shipped on /triage/analyze's TriageResponse.

Every check below is an honest, cheap heuristic — NOT a clinical-grade
validation engine. Each function's docstring says exactly what it does and
does not catch. For production-grade coverage these should be swapped for a
licensed clinical rules engine (e.g. First Databank, Medi-Span) behind the
same function signatures, matching the same scoping note already on
core/drug_interactions.py for the interaction table.
"""
import re
from typing import Dict, List, Optional, TypedDict


class CdsAlert(TypedDict):
    category: str  # ALLERGY / DUPLICATE_THERAPY / DOSAGE_CHANGE / INTERACTION
    severity: str  # INFO / WARNING / CRITICAL
    message: str
    explanation: str


def _norm(text: Optional[str]) -> str:
    return (text or "").strip().lower()


# ==========================================================
# a. Allergy cross-check
# ==========================================================

def check_allergy_conflicts(allergies_text: Optional[str], medicine_names: List[str]) -> List[CdsAlert]:
    """Case-insensitive substring/keyword match of the patient's free-text
    `allergies` field (User.allergies or FamilyProfile.allergies) against
    the medicine names being prescribed.

    Heuristic scoping (deliberate, not an oversight): this is plain string
    matching against whatever a patient or clinician typed into a free-text
    field — split on common separators (comma/semicolon/slash/newline) into
    terms, then checked as a substring against each medicine name. It is
    NOT a clinical-grade allergen/cross-reactivity database: it will not
    know that a "Penicillin" allergy also implicates "Amoxicillin", or that
    "NSAIDs" covers "Ibuprofen" and "Diclofenac". It only catches the literal
    text the patient recorded. Terms shorter than 3 characters are skipped
    to avoid noisy false positives (e.g. an allergy note containing a
    day-of-instruction... single-letter fragment). Always treat a hit as
    "ask the patient", not as a guaranteed match.
    """
    alerts: List[CdsAlert] = []
    if not allergies_text or not allergies_text.strip():
        return alerts

    terms = [t.strip().lower() for t in re.split(r"[,;/\n]+", allergies_text) if t.strip()]
    terms = [t for t in terms if len(t) >= 3]
    if not terms:
        return alerts

    for med in medicine_names:
        med_norm = _norm(med)
        if not med_norm:
            continue
        for term in terms:
            if term in med_norm or med_norm in term:
                alerts.append({
                    "category": "ALLERGY",
                    "severity": "CRITICAL",
                    "message": f"{med} may conflict with a documented allergy ('{term}').",
                    "explanation": (
                        f"The patient's allergy record includes '{term}', which matches '{med}' as a "
                        f"case-insensitive substring. This is a keyword heuristic against a free-text "
                        f"allergy note, not a clinical allergen/cross-reactivity database (it will not "
                        f"catch related drug-class allergies, e.g. Penicillin vs. Amoxicillin) — "
                        f"confirm directly with the patient before dispensing."
                    ),
                })
                break  # one alert per medicine is enough
    return alerts


# ==========================================================
# b. Duplicate-therapy check
# ==========================================================

def check_duplicate_therapy(new_medicine_names: List[str], active_medicine_names: List[str]) -> List[CdsAlert]:
    """Flags a newly-prescribed medicine that the patient already has an
    ACTIVE prescription for — "active" meaning the same start-date +
    parsed-duration logic the AI Doctor Assistant's patient-summary feature
    already uses for "active medicines" detection (see
    modules/ai_assist/router.py:_parse_duration_days / issue_prescription's
    interaction-check block in modules/ehr_sync/router.py, which this
    mirrors exactly so the two "what's currently active" answers never
    disagree).

    Matching is substring-based on the medicine name only (same convention
    as core/drug_interactions.py), which catches brand-name/strength
    variants like "Paracetamol" vs. "Paracetamol 650mg". It deliberately
    does NOT attempt same-drug-class detection (e.g. flagging a new NSAID
    on top of an active different NSAID): the codebase's only drug-class-ish
    data is PharmacyItem.generic_group, which is pharmacy-stock metadata for
    substitute lookups (not consistently populated, and scoped to one
    pharmacy's inventory) rather than a systematic clinical drug-class
    taxonomy — using it here would silently under- or over-fire depending on
    which pharmacy happened to stock the item. That's an honest scope cut,
    not an oversight.
    """
    alerts: List[CdsAlert] = []
    active_norm = [(_norm(m), m) for m in active_medicine_names if m and m.strip()]

    for med in new_medicine_names:
        med_norm = _norm(med)
        if not med_norm:
            continue
        for other_norm, other_orig in active_norm:
            if not other_norm:
                continue
            if other_norm in med_norm or med_norm in other_norm:
                alerts.append({
                    "category": "DUPLICATE_THERAPY",
                    "severity": "WARNING",
                    "message": f"{med} is already an active prescription for this patient.",
                    "explanation": (
                        f"The patient has an existing, not-yet-expired prescription for "
                        f"'{other_orig}' (active window computed from its start date + stated "
                        f"duration). Prescribing '{med}' again may be an intentional renewal or an "
                        f"unintended duplicate — please confirm before issuing."
                    ),
                })
                break  # one alert per new medicine
    return alerts


# ==========================================================
# c. Dosage-sanity flag
# ==========================================================

def check_dosage_changes(new_medicines: List[Dict[str, str]], history: List[Dict[str, str]]) -> List[CdsAlert]:
    """If the same medicine name was prescribed to this patient before with
    a meaningfully different dosage string, flag it for the doctor to
    double check.

    `new_medicines` / `history` are both lists of {"name", "dosage", ...}
    dicts (the same shape as a Prescription.medicines JSON entry). This is a
    simple string-diff heuristic — case/whitespace-normalized equality, not
    real pharmacological validation. It cannot tell that "500mg" and "0.5g"
    are the same dose, and it will also fire on a legitimate, intentional
    dose change (e.g. a deliberate step-down). It exists to catch likely
    typos or an overlooked history, not to make a dosing judgment — the
    doctor is always the one who decides.
    """
    alerts: List[CdsAlert] = []
    seen_names: set = set()

    for med in new_medicines:
        name = (med.get("name") or "").strip()
        dosage = (med.get("dosage") or "").strip()
        name_norm = _norm(name)
        if not name_norm or not dosage or name_norm in seen_names:
            continue

        for h in history:
            h_name = (h.get("name") or "").strip()
            h_dosage = (h.get("dosage") or "").strip()
            if _norm(h_name) != name_norm or not h_dosage:
                continue
            if _norm(h_dosage) != _norm(dosage):
                alerts.append({
                    "category": "DOSAGE_CHANGE",
                    "severity": "INFO",
                    "message": (
                        f"{name} was previously prescribed at a different dosage "
                        f"('{h_dosage}' vs. '{dosage}' now)."
                    ),
                    "explanation": (
                        f"A prior prescription for '{h_name}' used dosage '{h_dosage}'; this one uses "
                        f"'{dosage}'. This is a plain text comparison of dosage strings, not a "
                        f"pharmacological check — it cannot recognize equivalent doses written "
                        f"differently (e.g. '500mg' vs. '0.5g') and a real dose change may be exactly "
                        f"what's intended. Worth a quick double-check either way."
                    ),
                })
                seen_names.add(name_norm)
                break
    return alerts
