"""Verification suite for AIManager (requirement #11 of the AIManager
architecture spec).

IMPORTANT — execution status: this file was written in an environment
without shell/test-runner access (no `pytest` could be invoked to confirm
these pass). Treat every test here as UNVERIFIED until someone runs
`pytest tests/test_ai_manager.py -v` and confirms green. The tests are
written to be self-contained (no real network calls, no real API keys
needed) specifically so that first run should be possible immediately.

These tests exercise AIManager in isolation using FakeProvider test doubles
injected via `AIManager(providers={...})` — they do NOT hit the module-level
`get_ai_manager()` singleton used by the routers, and do NOT make real calls
to Gemini/OpenAI/Groq/Anthropic. Provider-specific SDK wiring (the actual
API call shape) is not covered here since it requires live credentials;
that's an integration-test concern for a real environment with keys set.
"""
import pytest

from ai.base import AIRequest, AITask, BaseAIProvider
from ai.errors import (
    AuthenticationError,
    JSONParseError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
)
from ai.manager import AIManager, AllProvidersFailedError
from ai.metrics import ai_metrics
from ai.providers.mock_provider import MockProvider


class FakeProvider(BaseAIProvider):
    """A configurable test double: fails in a scripted way N times, then
    (optionally) succeeds. Lets each test simulate exactly one failure mode
    without touching any real SDK."""

    def __init__(self, name: str, *, fail_with=None, fail_times: int = 0, vision: bool = True, **kwargs):
        super().__init__(api_key="fake-key", **kwargs)
        self.name = name
        self._fail_with = fail_with
        self._fail_times = fail_times
        self._vision = vision
        self.call_count = 0

    def supported_tasks(self):
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY}

    def supports_vision(self) -> bool:
        return self._vision

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return False

    async def generate(self, request: AIRequest) -> dict:
        self.call_count += 1
        if self._fail_times > 0 and self.call_count <= self._fail_times:
            raise self._fail_with(f"{self.name} simulated failure #{self.call_count}", provider=self.name)
        return {"severity_score": 10, "predicted_condition": f"ok-from-{self.name}",
                "home_remedies": "", "doctor_recommendation": "", "recovery_time": "",
                "status": "Normal", "confidence_score": 0.9, "explanation": "",
                "summary_text": f"ok-from-{self.name}",
                "extracted_text": "", "medicines_parsed": [], "confidence": 0.9}


@pytest.fixture(autouse=True)
def _reset_metrics():
    ai_metrics.reset_for_tests()
    yield
    ai_metrics.reset_for_tests()


@pytest.fixture(autouse=True)
def _pin_priority_env(monkeypatch):
    """Most tests below rely on the DEFAULT provider order (gemini before
    openai, etc.) to make assertions about fallback order deterministic.
    Pin it explicitly rather than relying on whatever happens to be in
    apps/backend_service/.env at test-run time — decouples this suite from
    unrelated .env edits. TestConfigDrivenPriority below explicitly
    overrides this per-test to verify the override mechanism itself works."""
    monkeypatch.delenv("AI_PROVIDER_PRIORITY_TRIAGE", raising=False)
    monkeypatch.delenv("AI_PROVIDER_PRIORITY_OCR", raising=False)
    monkeypatch.delenv("AI_PROVIDER_PRIORITY_DOCTOR_SUMMARY", raising=False)
    monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,openai,groq,anthropic,mock")


def _manager(*providers: BaseAIProvider, priority_env=None, monkeypatch=None) -> AIManager:
    reg = {p.name: p for p in providers}
    reg.setdefault("mock", MockProvider())
    return AIManager(providers=reg)


# ---------------------------------------------------------------------------
# 1. Each provider independently: capability flags + is_configured/available
# ---------------------------------------------------------------------------
class TestProviderIndependence:
    def test_mock_is_always_configured_and_available(self):
        m = MockProvider()
        assert m.is_configured() is True
        assert m.is_available() is True

    def test_unconfigured_provider_reports_not_available(self):
        p = FakeProvider("gemini", fail_with=None)
        p._api_key = None  # simulate missing key without needing the real subclasses
        status = p.health_status()
        assert status.configured is False
        assert status.available is False
        assert status.reason == "not_configured"

    def test_ocr_excludes_non_vision_providers(self):
        vision_provider = FakeProvider("gemini", vision=True)
        no_vision_provider = FakeProvider("groq", vision=False)
        manager = _manager(vision_provider, no_vision_provider)
        candidates = manager._candidates_for(AITask.OCR)
        names = [c.name for c in candidates]
        assert "groq" not in names
        assert "gemini" in names
        assert "mock" in names  # always eligible, MockProvider.supports_vision()=True

    def test_triage_without_image_includes_non_vision_providers(self):
        """Plain text/voice symptom checking must stay routable to every
        configured provider, including non-vision ones like Groq."""
        vision_provider = FakeProvider("gemini", vision=True)
        no_vision_provider = FakeProvider("groq", vision=False)
        manager = _manager(vision_provider, no_vision_provider)
        candidates = manager._candidates_for(AITask.TRIAGE, requires_vision=False)
        names = [c.name for c in candidates]
        assert "groq" in names
        assert "gemini" in names

    def test_triage_with_image_excludes_non_vision_providers(self):
        """Planning doc: the symptom checker accepts an OPTIONAL photo —
        when one is actually attached, only vision-capable providers may
        serve the request, same rule as OCR."""
        vision_provider = FakeProvider("gemini", vision=True)
        no_vision_provider = FakeProvider("groq", vision=False)
        manager = _manager(vision_provider, no_vision_provider)
        candidates = manager._candidates_for(AITask.TRIAGE, requires_vision=True)
        names = [c.name for c in candidates]
        assert "groq" not in names
        assert "gemini" in names


# ---------------------------------------------------------------------------
# 2-5. Simulated failure modes
# ---------------------------------------------------------------------------
class TestFailureModes:
    @pytest.mark.asyncio
    async def test_quota_exceeded_falls_back_to_next_provider(self):
        gemini = FakeProvider("gemini", fail_with=QuotaExceededError, fail_times=99)
        openai = FakeProvider("openai", fail_with=None, fail_times=0)
        manager = _manager(gemini, openai)

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.provider_used == "openai"
        assert outcome.fallback_occurred is True
        assert gemini.call_count == 1  # NOT retried — QuotaExceededError.retryable is False
        # Circuit breaker: gemini should now be marked unhealthy.
        assert gemini.health_status().available is False
        assert gemini.health_status().reason == "QuotaExceededError"

    @pytest.mark.asyncio
    async def test_authentication_error_not_retried_and_marks_unhealthy(self):
        gemini = FakeProvider("gemini", fail_with=AuthenticationError, fail_times=99)
        mock_only_manager = _manager(gemini)

        outcome = await mock_only_manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.provider_used == "mock"
        assert outcome.used_mock is True
        assert gemini.call_count == 1
        assert gemini.health_status().available is False

    @pytest.mark.asyncio
    async def test_timeout_is_retried_once_then_falls_back(self):
        gemini = FakeProvider("gemini", fail_with=TimeoutError_, fail_times=99)
        openai = FakeProvider("openai", fail_with=None, fail_times=0)
        manager = _manager(gemini, openai)

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.provider_used == "openai"
        # 1 initial attempt + 1 retry = 2 calls, per the retryable policy.
        assert gemini.call_count == 2
        assert outcome.retry_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_recovers_on_retry(self):
        """Provider fails once (rate limited) then succeeds on the retry —
        verifies retryable errors don't unnecessarily fall back if the retry
        itself succeeds."""
        gemini = FakeProvider("gemini", fail_with=RateLimitError, fail_times=1)
        manager = _manager(gemini)

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.provider_used == "gemini"
        assert gemini.call_count == 2
        assert outcome.retry_count == 1
        assert outcome.fallback_occurred is False

    @pytest.mark.asyncio
    async def test_invalid_json_not_retried_falls_back(self):
        gemini = FakeProvider("gemini", fail_with=JSONParseError, fail_times=99)
        openai = FakeProvider("openai", fail_with=None, fail_times=0)
        manager = _manager(gemini, openai)

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.provider_used == "openai"
        assert gemini.call_count == 1  # JSONParseError.retryable is False


# ---------------------------------------------------------------------------
# 6. Automatic fallback all the way to Mock
# ---------------------------------------------------------------------------
class TestFallbackToMock:
    @pytest.mark.asyncio
    async def test_all_real_providers_failing_reaches_mock(self):
        gemini = FakeProvider("gemini", fail_with=ProviderUnavailableError, fail_times=99)
        openai = FakeProvider("openai", fail_with=AuthenticationError, fail_times=99)
        manager = _manager(gemini, openai)

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.used_mock is True
        assert outcome.provider_used == "mock"
        assert outcome.data["explanation"] or outcome.data.get("summary_text")

    @pytest.mark.asyncio
    async def test_mock_provider_itself_never_raises(self):
        m = MockProvider()
        for task in (AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY):
            data = await m.generate(AIRequest(task=task, prompt="anything"))
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_no_mock_registered_raises_loudly_instead_of_returning_none(self):
        """Pathological case: if MockProvider were somehow removed from the
        registry (misconfiguration), AIManager must fail loudly rather than
        returning None to a caller that expects a dict."""
        gemini = FakeProvider("gemini", fail_with=AuthenticationError, fail_times=99)
        manager = AIManager(providers={"gemini": gemini})  # no "mock" key at all

        with pytest.raises(AllProvidersFailedError):
            await manager.run(AITask.TRIAGE, prompt="p")


# ---------------------------------------------------------------------------
# 7. Schema consistency — MockProvider's dict must satisfy the real response
#    models used by the routers, without importing modules.* here (ai/ has
#    no dependency on modules/, by design — see manager.py docstring).
# ---------------------------------------------------------------------------
class TestSchemaConsistency:
    @pytest.mark.asyncio
    async def test_triage_mock_output_has_all_triage_response_fields(self):
        expected_fields = {
            "severity_score", "predicted_condition", "home_remedies",
            "doctor_recommendation", "recovery_time", "status",
            "confidence_score", "explanation", "possible_causes",
            "first_aid", "side_effects", "treatment_options",
            "untreated_outcome", "specialist_type", "language_detected",
        }
        m = MockProvider()
        data = await m.generate(AIRequest(task=AITask.TRIAGE, prompt="p"))
        missing = expected_fields - set(data.keys())
        assert not missing, f"MockProvider TRIAGE output missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_ocr_mock_output_has_all_ocr_response_fields(self):
        expected_fields = {"extracted_text", "medicines_parsed", "confidence"}
        m = MockProvider()
        data = await m.generate(AIRequest(task=AITask.OCR, prompt="p"))
        missing = expected_fields - set(data.keys())
        assert not missing, f"MockProvider OCR output missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_every_real_provider_declares_at_least_one_task(self):
        """Every registered provider class must claim at least one
        supported task — a provider supporting nothing would be silently
        unreachable and is almost certainly a registration bug."""
        from ai.providers import PROVIDER_CLASSES

        for name, cls in PROVIDER_CLASSES.items():
            instance = cls(api_key=None) if name != "mock" else cls()
            assert len(instance.supported_tasks()) > 0, f"{name} declares no supported tasks"


# ---------------------------------------------------------------------------
# 8. Logging — provider selected/used, latency, retry count, fallback reason.
# ---------------------------------------------------------------------------
class TestLogging:
    @pytest.mark.asyncio
    async def test_successful_request_logs_required_fields(self, caplog):
        import logging
        caplog.set_level(logging.INFO, logger="gramcare.ai.manager")

        gemini = FakeProvider("gemini")
        manager = _manager(gemini)
        await manager.run(AITask.TRIAGE, prompt="secret symptom text should not appear in logs")

        joined = "\n".join(r.message for r in caplog.records)
        assert "provider_selected=gemini" in joined
        assert "provider_used=gemini" in joined
        assert "latency_ms=" in joined
        assert "retry_count=" in joined
        # PII/prompt must never be logged.
        assert "secret symptom text" not in joined

    @pytest.mark.asyncio
    async def test_failure_logs_error_category(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="gramcare.ai.manager")

        gemini = FakeProvider("gemini", fail_with=AuthenticationError, fail_times=99)
        manager = _manager(gemini)
        await manager.run(AITask.TRIAGE, prompt="p")

        joined = "\n".join(r.message for r in caplog.records)
        assert "category=AuthenticationError" in joined


# ---------------------------------------------------------------------------
# 9. Metrics
# ---------------------------------------------------------------------------
class TestMetrics:
    @pytest.mark.asyncio
    async def test_success_recorded_in_metrics(self):
        gemini = FakeProvider("gemini")
        manager = _manager(gemini)
        await manager.run(AITask.TRIAGE, prompt="p")

        snap = ai_metrics.snapshot()
        assert snap["by_provider"]["gemini"]["triage"]["requests"] == 1
        assert snap["by_provider"]["gemini"]["triage"]["failures"] == 0

    @pytest.mark.asyncio
    async def test_failure_and_fallback_recorded_in_metrics(self):
        gemini = FakeProvider("gemini", fail_with=QuotaExceededError, fail_times=99)
        openai = FakeProvider("openai")
        manager = _manager(gemini, openai)
        await manager.run(AITask.TRIAGE, prompt="p")

        snap = ai_metrics.snapshot()
        assert snap["by_provider"]["gemini"]["triage"]["failures"] == 1
        assert snap["by_provider"]["gemini"]["triage"]["failures_by_type"]["QuotaExceededError"] == 1
        assert snap["by_provider"]["openai"]["triage"]["requests"] == 1
        assert snap["fallback_count_by_task"]["triage"] == 1


# ---------------------------------------------------------------------------
# Config-driven priority (requirement #2) and always-mock guarantee (#12)
# ---------------------------------------------------------------------------
class TestConfigDrivenPriority:
    def test_priority_is_read_from_env_not_hardcoded(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "openai,gemini")
        from ai.config import get_priority
        order = get_priority(AITask.DOCTOR_SUMMARY)
        assert order == ["openai", "gemini", "mock"]

    def test_mock_always_appended_even_if_omitted(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini")
        from ai.config import get_priority
        assert get_priority(AITask.TRIAGE)[-1] == "mock"

    def test_missing_provider_registration_is_skipped_not_fatal(self):
        """If configuration lists a provider name AIManager doesn't have
        registered, selection must skip it rather than raising."""
        manager = AIManager(providers={"mock": MockProvider()})
        candidates = manager._candidates_for(AITask.TRIAGE)
        assert any(c.name == "mock" for c in candidates)
