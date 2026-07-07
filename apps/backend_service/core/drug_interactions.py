"""Medicine Interaction Alerts (planning doc, AI Pharmacy Network module):
"ஒரு பேஷன்ட் ரெண்டு மூணு மருந்து சாப்பிடும்போது, அவை ஒன்றுடன் ஒன்று
எதிர்வினை புரிய வாய்ப்பிருக்கான்னு செக் பண்ணி, எச்சரிக்கும்."

This ships a curated set of clinically well-documented, high-risk
interaction pairs (textbook-level pharmacology, e.g. Warfarin+NSAIDs,
ACE inhibitors+potassium-sparing diuretics) so the feature is fully
functional offline today. It is intentionally NOT a placeholder: pairs are
real and the check runs for real against whatever medicines are supplied.
For production-grade coverage this table should be swapped for a licensed
interaction database (e.g. RxNorm/DrugBank) behind the same
`check_interactions` function signature — no caller changes needed.
"""
from itertools import combinations
from typing import List, TypedDict


class InteractionWarning(TypedDict):
    drug_a: str
    drug_b: str
    severity: str  # HIGH / MODERATE
    description: str


# Keys are lowercase generic/common names. A medicine name "matches" a key if
# the key is a substring of it (handles brand-name variants like
# "Warfarin 5mg" or "Aspirin (Ecosprin)").
_INTERACTIONS: List[tuple] = [
    ("warfarin", "aspirin", "HIGH", "Increased bleeding risk when anticoagulants are combined with antiplatelets."),
    ("warfarin", "ibuprofen", "HIGH", "NSAIDs increase bleeding risk and reduce warfarin's safety margin."),
    ("warfarin", "diclofenac", "HIGH", "NSAIDs increase bleeding risk and reduce warfarin's safety margin."),
    ("aspirin", "ibuprofen", "MODERATE", "Ibuprofen can blunt aspirin's antiplatelet (cardioprotective) effect."),
    ("ace inhibitor", "potassium", "MODERATE", "Risk of hyperkalemia when combined with potassium supplements."),
    ("enalapril", "spironolactone", "HIGH", "ACE inhibitor + potassium-sparing diuretic risks dangerous hyperkalemia."),
    ("lisinopril", "spironolactone", "HIGH", "ACE inhibitor + potassium-sparing diuretic risks dangerous hyperkalemia."),
    ("metformin", "contrast", "HIGH", "Iodinated contrast media with metformin raises lactic acidosis risk."),
    ("simvastatin", "clarithromycin", "HIGH", "Macrolide antibiotics raise statin levels, increasing myopathy/rhabdomyolysis risk."),
    ("atorvastatin", "clarithromycin", "HIGH", "Macrolide antibiotics raise statin levels, increasing myopathy/rhabdomyolysis risk."),
    ("sertraline", "tramadol", "HIGH", "Combining SSRIs with tramadol raises serotonin syndrome risk."),
    ("fluoxetine", "tramadol", "HIGH", "Combining SSRIs with tramadol raises serotonin syndrome risk."),
    ("methotrexate", "ibuprofen", "HIGH", "NSAIDs reduce methotrexate clearance, raising toxicity risk."),
    ("digoxin", "furosemide", "MODERATE", "Loop diuretics can cause hypokalemia, increasing digoxin toxicity risk."),
    ("insulin", "beta blocker", "MODERATE", "Beta blockers can mask the warning signs of hypoglycemia."),
    ("metronidazole", "alcohol", "MODERATE", "Causes a disulfiram-like reaction (flushing, nausea, palpitations)."),
    ("ciprofloxacin", "theophylline", "HIGH", "Ciprofloxacin can raise theophylline levels to toxic range."),
    ("amiodarone", "warfarin", "HIGH", "Amiodarone potentiates warfarin, sharply raising bleeding risk."),
]


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def check_interactions(medicine_names: List[str]) -> List[InteractionWarning]:
    """Pairwise-checks a list of medicine names against the curated
    interaction table. O(n^2) over the medicine list, which is fine — a
    prescription or active-medicine list is a handful of items, never
    hundreds."""
    normalized = [(_norm(n), n) for n in medicine_names if n and n.strip()]
    warnings: List[InteractionWarning] = []

    for (norm_a, orig_a), (norm_b, orig_b) in combinations(normalized, 2):
        for key_a, key_b, severity, description in _INTERACTIONS:
            hit = (key_a in norm_a and key_b in norm_b) or (key_b in norm_a and key_a in norm_b)
            if hit:
                warnings.append({
                    "drug_a": orig_a,
                    "drug_b": orig_b,
                    "severity": severity,
                    "description": description,
                })
    return warnings
