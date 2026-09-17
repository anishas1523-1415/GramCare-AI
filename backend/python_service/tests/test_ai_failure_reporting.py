"""How AI failures are reported to patients, and where a pasted key goes.

Every case here was a real production failure: an unfunded OpenAI account
and a retired Groq model together made the apps say "AI limit reached" when
Gemini had only hiccuped, and a key a patient pasted in was sent to every
provider rather than the one that issued it.
"""
import pytest

from ai.base import AIRequest, AITask, BaseAIProvider
from ai.errors import (
    AuthenticationError,
    BillingError,
    ModelNotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    classify_exception,
)
from ai.keypool import KeyPool
from ai.manager import AIManager, provider_for_user_key
from ai.metrics import ai_metrics
from ai.providers.mock_provider import MockProvider


class RecordingProvider(BaseAIProvider):
    """Fails with `fail_with` on every call (or succeeds when None), and
    records which key each call was made with."""

    def __init__(self, name, *, fail_with=None, fail_for_user_key=None):
        super().__init__(api_key="server-key")
        self.name = name
        self._fail_with = fail_with
        self._fail_for_user_key = fail_for_user_key
        self.keys_seen: list = []

    def supported_tasks(self):
        return {AITask.TRIAGE}

    def supports_vision(self):
        return True

    def supports_json(self):
        return True

    def supports_streaming(self):
        return False

    async def generate(self, request: AIRequest) -> dict:
        self.keys_seen.append(request.user_api_key)
        if request.user_api_key and self._fail_for_user_key:
            raise self._fail_for_user_key("user key failed", provider=self.name)
        if self._fail_with:
            raise self._fail_with("simulated", provider=self.name)
        return {"severity_score": 10, "predicted_condition": f"ok-from-{self.name}",
                "home_remedies": "", "doctor_recommendation": "", "recovery_time": "",
                "status": "Normal", "confidence_score": 0.9, "explanation": ""}


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    ai_metrics.reset_for_tests()
    monkeypatch.delenv("AI_PROVIDER_PRIORITY_TRIAGE", raising=False)
    monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,openai,groq,anthropic,mock")
    yield
    ai_metrics.reset_for_tests()


def _manager(*providers):
    reg = {p.name: p for p in providers}
    reg["mock"] = MockProvider()
    return AIManager(providers=reg)


# --- classification ---------------------------------------------------------

def test_openai_out_of_credits_is_billing_not_a_limit():
    msg = ("Error code: 429 - {'error': {'message': 'You have no credits remaining.', "
           "'type': 'insufficient_quota', 'code': 'credit_balance_exhausted'}}")
    err = classify_exception(Exception(msg), provider="openai")
    assert isinstance(err, BillingError)
    assert err.retryable is False


def test_retired_model_is_reported_as_missing_model():
    msg = ("Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` "
           "does not exist or you do not have access to it.', 'code': 'model_not_found'}}")
    assert isinstance(classify_exception(Exception(msg), provider="groq"), ModelNotFoundError)


# --- the "AI limit reached" flag --------------------------------------------

@pytest.mark.asyncio
async def test_hiccup_plus_unfunded_account_is_not_reported_as_a_limit():
    """The exact production combination: Gemini briefly unavailable, OpenAI
    with no credits, Groq on a retired model. None of that is a limit."""
    manager = _manager(
        RecordingProvider("gemini", fail_with=ProviderUnavailableError),
        RecordingProvider("openai", fail_with=BillingError),
        RecordingProvider("groq", fail_with=ModelNotFoundError),
    )
    outcome = await manager.run(AITask.TRIAGE, prompt="p")

    assert outcome.used_mock is True
    assert outcome.quota_exhausted is False
    assert outcome.failures == {
        "gemini": "ProviderUnavailableError",
        "openai": "BillingError",
        "groq": "ModelNotFoundError",
    }


@pytest.mark.asyncio
async def test_every_provider_genuinely_limited_is_still_reported_as_a_limit():
    manager = _manager(
        RecordingProvider("gemini", fail_with=RateLimitError),
        RecordingProvider("openai", fail_with=QuotaExceededError),
    )
    outcome = await manager.run(AITask.TRIAGE, prompt="p")
    assert outcome.used_mock is True
    assert outcome.quota_exhausted is True


def test_a_pool_of_unfunded_keys_is_not_out_of_quota():
    pool = KeyPool.from_keys("openai", ["sk-a", "sk-b"])
    pool.mark_dead("sk-a")
    pool.mark_dead("sk-b")
    assert pool.all_exhausted() is False
    assert pool.dead_count() == 2

    pool = KeyPool.from_keys("gemini", ["k1", "k2"])
    pool.mark_exhausted("k1")
    pool.mark_exhausted("k2")
    assert pool.all_exhausted() is True


# --- where a pasted key goes -------------------------------------------------

@pytest.mark.parametrize("key,owner", [
    ("AIzaSyExample", "gemini"),
    ("AQ.Ab8RN6Example", "gemini"),
    ("sk-proj-Example", "openai"),
    ("sk-ant-api03-Example", "anthropic"),
    ("gsk_Example", "groq"),
])
def test_key_prefix_identifies_its_issuer(key, owner):
    assert provider_for_user_key(key) == owner


@pytest.mark.asyncio
async def test_pasted_key_goes_only_to_its_issuer_and_is_tried_first():
    gemini = RecordingProvider("gemini")
    openai = RecordingProvider("openai")
    groq = RecordingProvider("groq")
    # Groq's key: Groq must go first even though Gemini is first by priority.
    manager = _manager(gemini, openai, groq)

    outcome = await manager.run(AITask.TRIAGE, prompt="p", user_api_key="gsk_patient_key")

    assert outcome.provider_used == "groq"
    assert groq.keys_seen == ["gsk_patient_key"]
    assert gemini.keys_seen == [] and openai.keys_seen == []


@pytest.mark.asyncio
async def test_rejected_pasted_key_is_reported_and_other_providers_never_see_it():
    gemini = RecordingProvider("gemini", fail_for_user_key=AuthenticationError)
    openai = RecordingProvider("openai", fail_with=BillingError)
    groq = RecordingProvider("groq", fail_with=ModelNotFoundError)
    manager = _manager(gemini, openai, groq)

    outcome = await manager.run(AITask.TRIAGE, prompt="p", user_api_key="AIzaSyWrong")

    assert outcome.used_mock is True
    assert outcome.user_key_error == "AuthenticationError"
    assert "AIzaSyWrong" not in openai.keys_seen
    assert "AIzaSyWrong" not in groq.keys_seen


@pytest.mark.asyncio
async def test_one_patients_bad_key_does_not_take_gemini_away_from_everyone():
    """A user's rejected key used to mark the provider unhealthy for the
    whole health-cache window, blocking every other user's requests."""
    gemini = RecordingProvider("gemini", fail_for_user_key=AuthenticationError)
    manager = _manager(gemini)

    await manager.run(AITask.TRIAGE, prompt="p", user_api_key="AIzaSyWrong")
    assert gemini.health_status().available is True

    # The next patient, with no key of their own, still gets Gemini.
    outcome = await manager.run(AITask.TRIAGE, prompt="p")
    assert outcome.provider_used == "gemini"


# --- placeholders are not medical records -----------------------------------

def test_offline_placeholder_answer_is_not_saved_as_a_triage(client, patient_token):
    """With no working provider the answer is MockProvider's placeholder.
    It used to be written to triage_logs like a diagnosis: 13 of them
    reached production and formed an outbreak cluster of a condition that
    does not exist."""
    from database import SessionLocal
    import models
    from tests.conftest import auth

    with SessionLocal() as db:
        before = db.query(models.TriageLog).count()

    res = client.post("/api/v1/triage/analyze", headers=auth(patient_token), json={
        "symptoms_text": "fever and cough", "patient_id": "self", "age": 30,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ai_engine"] == "mock"

    with SessionLocal() as db:
        assert db.query(models.TriageLog).count() == before


def test_stored_placeholders_are_left_out_of_outbreak_clusters(client):
    from database import SessionLocal
    import models
    from tests.conftest import _register_and_login, auth

    with SessionLocal() as db:
        for _ in range(5):
            db.add(models.TriageLog(symptoms_text="x", ai_severity_score=50,
                                    ai_predicted_condition="Unknown (AI Engines Unavailable)",
                                    ai_confidence=0.0))
            db.add(models.TriageLog(symptoms_text="x", ai_severity_score=60,
                                    ai_predicted_condition="Dengue Fever",
                                    ai_confidence=0.8))
        db.commit()

    admin = _register_and_login(client, "placeholder_cluster_admin", "ADMIN")
    clusters = client.get("/api/v1/analytics/health-clusters?days=7&min_cases=3",
                          headers=auth(admin)).json()
    conditions = {c["condition"] for c in clusters}
    assert "dengue fever" in conditions
    assert not any(c.startswith("unknown (") for c in conditions)
