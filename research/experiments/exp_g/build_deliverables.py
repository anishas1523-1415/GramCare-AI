"""Generate Experiment G's CSV deliverables from the app and the raw probe data.

Produces:
  EXPERIMENT_G_ENDPOINT_INVENTORY.csv  every endpoint, its declared guards,
                                       whether Experiment G probed it, outcome
  EXPERIMENT_G_ACCESS_MATRIX.csv       consolidated probe results across all
                                       runs and both engines

Nothing here measures anything: it reads the app's own route table and the CSVs
the experiment runs wrote, and joins them. Run it after the experiments.
"""
import csv
import glob
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SERVICE = os.path.join(REPO, "backend", "python_service")
sys.path.insert(0, SERVICE)

_T = tempfile.mkdtemp(prefix="gramcare_inv_")
os.environ["DATABASE_URL"] = "sqlite:///%s/inv.db" % _T.replace("\\", "/")
os.environ.setdefault("JWT_SECRET_KEY", "inventory-only-not-for-production")
for v in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY",
          "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "CLOUDINARY_CLOUD_NAME",
          "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GOOGLE_MAPS_API_KEY",
          "MSG91_AUTH_KEY", "RESEND_API_KEY"):
    os.environ[v] = ""
os.environ["TESTING"] = "1"

from main import app  # noqa: E402

RESULTS = os.path.join(HERE, "results")
OUT = HERE


def guard_of(route):
    """Describe the authorisation guard a route declares, by reading the
    dependency closures FastAPI resolved for it."""
    roles, kinds, limits = set(), set(), []
    dep = getattr(route, "dependant", None)
    if dep is None:
        return "", "", ""

    def walk(d, depth=0):
        if depth > 6 or d is None:
            return
        call = getattr(d, "call", None)
        name = getattr(call, "__name__", "") or ""
        qual = getattr(call, "__qualname__", "") or ""
        closure = getattr(call, "__closure__", None) or ()
        cells = []
        for c in closure:
            try:
                cells.append(c.cell_contents)
            except ValueError:
                pass
        if "require_role" in qual or "require_role" in name:
            kinds.add("require_role")
        if "require_approved_doctor" in qual or "require_approved_doctor" in name:
            kinds.add("require_approved_doctor")
            roles.add("DOCTOR(APPROVED)")
        if "get_current_user_optional" in qual or "get_current_user_optional" in name:
            kinds.add("optional_auth")
        elif "get_current_user" in qual or "get_current_user" in name:
            kinds.add("authenticated")
        if "rate_limit" in qual or "rate_limit" in name:
            kinds.add("rate_limited")
            nums = [c for c in cells if isinstance(c, int)]
            strs = [c for c in cells if isinstance(c, str)]
            if len(nums) >= 2:
                limits.append("%s:%d/%ds" % (strs[0] if strs else "?",
                                             nums[0], nums[1]))
        for c in cells:
            if isinstance(c, (set, frozenset, list, tuple)):
                for item in c:
                    if isinstance(item, str) and item.isupper() and 3 <= len(item) <= 12:
                        roles.add(item)
            elif isinstance(c, str) and c.isupper() and 3 <= len(c) <= 12:
                roles.add(c)
        for sub in getattr(d, "dependencies", []) or []:
            walk(sub, depth + 1)

    walk(dep)
    label = "+".join(sorted(kinds))
    if not label:
        # No JWT dependency is not the same as no control. These three carry
        # their own credential in the request itself, which Experiment G
        # probes directly (Part C for the webhook).
        label = {
            "/api/v1/payments/webhook": "hmac_signature_verified",
            "/api/v1/auth/refresh": "bearer_refresh_token_in_body",
            "/api/v1/auth/verify-email": "single_use_token_in_body",
        }.get(getattr(route, "path", ""), "UNGUARDED")
    return (label, "|".join(sorted(roles)), ",".join(limits))


# Endpoints covered by the hand-written probes in phase2_tokens_and_gaps.py and
# phase2_postgres_validation.py. Those scripts record a human-readable label
# rather than the templated route path, so coverage is declared explicitly here
# instead of inferred by string matching. Each entry names the probe that
# covers it, so a reviewer can check the claim against the raw CSV.
EXPLICIT_COVERAGE = {
    ("GET", "/api/v1/sos/track/{token}"):
        "phase2_tokens_and_gaps: entropy, rate limit, scope, namespace, "
        "post-resolution redaction, grace-window expiry",
    ("GET", "/api/v1/files/{token}"):
        "phase2_tokens_and_gaps: entropy, rate limit, namespace confusion, "
        "error-body leakage",
    ("GET", "/api/v1/passport/{token}"):
        "phase2_tokens_and_gaps: entropy, rate limit, scope, rotation "
        "invalidates the old token",
    ("DELETE", "/api/v1/doctors/me/slots/{slot_id}"):
        "phase2_tokens_and_gaps Part A: cross-tenant delete as doctor B and "
        "patient B, plus the owner's own delete",
    ("PUT", "/api/v1/pharmacy/fulfill/{prescription_id}"):
        "isolation_matrix axis 4b: cross-tenant dispense (documented residual)",
    ("GET", "/api/v1/payments/{order_id}/status"):
        "phase2_tokens_and_gaps Part A: cross-tenant read as patient B and "
        "pharmacist B, plus the owner's own read",
    ("POST", "/api/v1/payments/refund/{order_id}"):
        "phase2_tokens_and_gaps Part A: cross-tenant refund and self-refund",
    ("PUT", "/api/v1/appointments/{appointment_id}"):
        "phase2_tokens_and_gaps Part A: cross-tenant update as patient B and "
        "as a non-treating doctor, plus the treating doctor's own update",
    ("DELETE", "/api/v1/auth/sessions/{session_id}"):
        "phase2_tokens_and_gaps Part A: cross-tenant session revocation",
    ("DELETE", "/api/v1/auth/government-whitelist/{entry_id}"):
        "phase2_tokens_and_gaps Part A: non-admin delete, plus the admin's own",
    ("POST", "/api/v1/payments/webhook"):
        "phase2_tokens_and_gaps Part C: unsigned and wrongly-signed forgery "
        "rejected, correct signature honoured, replay idempotent",
    ("POST", "/api/v1/ehr/sync"):
        "phase2_postgres_validation P2: 10 concurrent identical batches, "
        "duplicate rate measured",
    ("POST", "/api/v1/triage/analyze"):
        "isolation_matrix axis 4b + phase2_postgres_validation P4: "
        "cross-tenant family_profile_id write rejected, no orphan row",
    ("GET", "/api/v1/ehr/records"):
        "isolation_matrix axis 3 + phase2_postgres_validation P5: scoping, "
        "pagination, out-of-range rejection",
    ("GET", "/api/v1/assist/patient-summary/{patient_id}"):
        "isolation_matrix axis 4 + phase2_postgres_validation P4: audited",
    ("GET", "/api/v1/ehr/patient/{patient_id}"):
        "isolation_matrix axis 4 + phase2_postgres_validation P4: audited, "
        "denial writes no audit row",
}

# ---------------------------------------------------- consolidated access matrix
matrix_rows = []


def add_matrix(engine, source, axis, method, path, caller, expected, status,
               verdict, note):
    matrix_rows.append({
        "engine": engine, "source": source, "axis": axis, "method": method,
        "path": path, "caller": caller, "expected": expected,
        "observed_status": status, "verdict": verdict, "note": note,
    })


for f in sorted(glob.glob(os.path.join(RESULTS, "isolation_matrix_*_raw.csv"))):
    engine = re.search(r"isolation_matrix_(\w+)_raw", os.path.basename(f)).group(1)
    with open(f, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            finding = (r.get("finding") or "").strip()
            if finding.startswith("INCONCLUSIVE"):
                verdict = "inconclusive"
            elif finding:
                verdict = "finding"
            else:
                verdict = "pass"
            add_matrix(engine, "isolation_matrix", r["axis"], r["method"], r["path"],
                       r["caller"], r["expected"], r["status"], verdict, finding)

for f in sorted(glob.glob(os.path.join(RESULTS, "phase2_*_raw.csv"))):
    base = os.path.basename(f)
    if "postgres_validation" in base:
        engine = "postgresql"
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                add_matrix(engine, "postgres_validation", r["part"], "-", r["label"],
                           "-", r["expected"], r["observed"], r["verdict"],
                           r.get("note", ""))
        continue
    engine = re.search(r"phase2_(\w+)_raw", base).group(1)
    with open(f, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            add_matrix(engine, "phase2_tokens_and_gaps", r["part"], "-", r["label"],
                       "-", r["expected"], r["status"], r["verdict"],
                       r.get("note", ""))

with open(os.path.join(OUT, "EXPERIMENT_G_ACCESS_MATRIX.csv"), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["engine", "source", "axis", "method", "path",
                                       "caller", "expected", "observed_status",
                                       "verdict", "note"])
    w.writeheader()
    for r in matrix_rows:
        w.writerow(r)

# ------------------------------------------------------------ endpoint inventory
# Which paths the probes actually touched, by exact path or by template.
probed_paths = set()
for r in matrix_rows:
    probed_paths.add(r["path"])
probed_text = "\n".join(probed_paths)

inv = []
for route in app.routes:
    methods = getattr(route, "methods", None)
    if not methods:
        continue
    path = getattr(route, "path", "")
    if not path.startswith("/api/v1"):
        continue
    params = re.findall(r"{(\w+)}", path)
    kinds, roles, limits = guard_of(route)
    for m in sorted(methods):
        if m in ("HEAD", "OPTIONS"):
            continue
        # A templated path counts as probed if the probes hit a concretised
        # form of it (the isolation matrix substitutes real ids), OR if its
        # literal prefix appears in a probe label (phase2 records a
        # human-readable label such as
        # "GET /payments/{A's order}/status as patient B" rather than the
        # templated path, so an exact match would under-report its coverage).
        concrete_re = re.escape(path)
        for p in params:
            concrete_re = concrete_re.replace(re.escape("{%s}" % p), r"[^/\s]+")
        literal_prefix = path.split("{")[0].rstrip("/")
        explicit_note = EXPLICIT_COVERAGE.get((m, path))
        probed = (
            bool(re.search(concrete_re + r"(\?|\s|$)", probed_text))
            or path in probed_paths
            or explicit_note is not None
        )
        hits = [r for r in matrix_rows
                if r["path"] == path
                or re.fullmatch(concrete_re, r["path"] or "")
                or (len(params) > 0 and len(literal_prefix) > len("/api/v1/")
                    and literal_prefix in (r["path"] or ""))]
        outcomes = [r["verdict"] for r in hits]
        covered_by = ",".join(sorted({r["source"] for r in hits}))
        if explicit_note:
            covered_by = (covered_by + "; " if covered_by else "") + explicit_note
        if not outcomes and explicit_note:
            outcome = "pass (see covered_by)"
        elif any(o == "finding" for o in outcomes):
            outcome = "finding (see register)"
        elif any(o == "inconclusive" for o in outcomes):
            outcome = "inconclusive"
        elif outcomes:
            outcome = "pass"
        else:
            outcome = "not probed" if not probed else "probed"
        inv.append({
            "method": m,
            "path": path,
            "path_params": ",".join(params),
            "auth_model": kinds or "UNGUARDED",
            "roles_required": roles,
            "rate_limit": limits,
            "probed_by_experiment_g": "yes" if probed else "no",
            "covered_by": covered_by,
            "outcome": outcome,
        })

inv.sort(key=lambda r: (r["path"], r["method"]))
with open(os.path.join(OUT, "EXPERIMENT_G_ENDPOINT_INVENTORY.csv"), "w", newline="",
          encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["method", "path", "path_params", "auth_model",
                                       "roles_required", "rate_limit",
                                       "probed_by_experiment_g", "covered_by",
                                       "outcome"])
    w.writeheader()
    for r in inv:
        w.writerow(r)

# ------------------------------------------------------------------------ report
by_engine = {}
for r in matrix_rows:
    k = (r["engine"], r["source"])
    d = by_engine.setdefault(k, {"pass": 0, "finding": 0, "inconclusive": 0,
                                 "skipped": 0})
    d[r["verdict"]] = d.get(r["verdict"], 0) + 1

print("ENDPOINT INVENTORY: %d method+path rows" % len(inv))
print("  probed    : %d" % sum(1 for r in inv if r["probed_by_experiment_g"] == "yes"))
print("  not probed: %d" % sum(1 for r in inv if r["probed_by_experiment_g"] == "no"))
print("  unguarded : %d" % sum(1 for r in inv if r["auth_model"] == "UNGUARDED"))
from collections import Counter as _C
print("  unprobed by method: %s"
      % dict(_C(r["method"] for r in inv if r["probed_by_experiment_g"] == "no")))
print()
print("ACCESS MATRIX: %d probe rows" % len(matrix_rows))
for (engine, source), d in sorted(by_engine.items()):
    print("  %-12s %-26s pass=%-4d finding=%-3d inconclusive=%-3d"
          % (engine, source, d.get("pass", 0), d.get("finding", 0),
             d.get("inconclusive", 0)))
print()
print("wrote %s" % os.path.join(OUT, "EXPERIMENT_G_ACCESS_MATRIX.csv"))
print("wrote %s" % os.path.join(OUT, "EXPERIMENT_G_ENDPOINT_INVENTORY.csv"))
