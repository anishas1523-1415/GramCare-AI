"""Key rotation across multiple API keys per provider.

Every provider GramCare AI uses is on a free tier with a daily request cap.
With one key, hitting that cap took every AI feature in every app down for
the rest of the day — the "AI Engines Unavailable" card users reported
seeing on all but roughly one attempt in a hundred. These tests cover the
rotation that turns N free keys into N times the headroom, and the signal
the apps use to offer the user their own key once even that runs out.
"""
import pytest

from ai.base import AIRequest, AITask, BaseAIProvider
from ai.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
)
from ai.keypool import DEFAULT_COOLDOWN_SECONDS, KeyPool
from ai.manager import AIManager
from ai.metrics import ai_metrics
from ai.providers.mock_provider import MockProvider


@pytest.fixture(autouse=True)
def _reset_metrics():
    ai_metrics.reset_for_tests()
    yield
    ai_metrics.reset_for_tests()


class RotatingProvider(BaseAIProvider):
    """Fails for every key named in `dead`, succeeds for anything else, and
    records the exact order of keys it was handed."""

    def __init__(self, name="gemini", *, dead=(), error=QuotaExceededError, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self._dead = set(dead)
        self._error = error
        self.keys_tried: list[str] = []

    def supported_tasks(self):
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY}

    def supports_vision(self) -> bool:
        return True

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return False

    async def generate(self, request: AIRequest) -> dict:
        async def _attempt(key: str) -> dict:
            self.keys_tried.append(key)
            if key in self._dead:
                raise self._error(f"{key} is spent", provider=self.name)
            return {"predicted_condition": f"answered-with-{key}", "severity_score": 10}

        return await self.run_with_rotation(request, _attempt)


def _provider(**kwargs):
    return RotatingProvider(key_pool=KeyPool.from_keys("gemini", ["k1", "k2", "k3"]), **kwargs)


def _req(**kwargs):
    return AIRequest(task=AITask.TRIAGE, prompt="p", **kwargs)


class TestKeyPool:
    def test_duplicate_keys_are_not_counted_as_extra_headroom(self):
        pool = KeyPool.from_keys("gemini", ["a", "a", "b"])
        assert len(pool) == 2

    def test_blank_entries_are_ignored(self):
        pool = KeyPool.from_keys("gemini", ["a", "", "   ", "b"])
        assert len(pool) == 2

    def test_from_env_merges_plural_and_singular(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "a, b")
        monkeypatch.setenv("GEMINI_API_KEY", "c")
        pool = KeyPool.from_env("gemini", "GEMINI_API_KEYS", "GEMINI_API_KEY")
        assert len(pool) == 3

    def test_from_env_still_works_with_only_the_singular_var(self, monkeypatch):
        """An existing single-key deployment must keep working untouched."""
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "only-one")
        pool = KeyPool.from_env("gemini", "GEMINI_API_KEYS", "GEMINI_API_KEY")
        assert len(pool) == 1
        assert pool.first_usable() == "only-one"

    def test_exhausted_key_is_skipped_until_its_cooldown_passes(self):
        pool = KeyPool.from_keys("gemini", ["a", "b"])
        pool.mark_exhausted("a")
        assert list(pool.usable_keys()) == ["b"]
        assert pool.available_count() == 1
        assert pool.all_exhausted() is False

    def test_all_exhausted_only_when_every_key_is_cooling(self):
        pool = KeyPool.from_keys("gemini", ["a", "b"])
        pool.mark_exhausted("a")
        pool.mark_exhausted("b")
        assert pool.all_exhausted() is True
        assert pool.seconds_until_recovery() == pytest.approx(DEFAULT_COOLDOWN_SECONDS, abs=5)

    def test_an_empty_pool_is_not_exhausted_it_is_unconfigured(self):
        """The apps show different messages for the two, so they must not
        collapse into one state."""
        pool = KeyPool.from_keys("gemini", [])
        assert pool.configured is False
        assert pool.all_exhausted() is False

    def test_a_working_key_clears_its_own_cooldown(self):
        pool = KeyPool.from_keys("gemini", ["a"])
        pool.mark_rate_limited("a")
        assert pool.all_exhausted() is True
        pool.mark_ok("a")
        assert pool.all_exhausted() is False

    def test_snapshot_never_exposes_a_whole_key(self):
        pool = KeyPool.from_keys("gemini", ["supersecretkeyvalue"])
        rendered = str(pool.snapshot())
        assert "supersecretkeyvalue" not in rendered
        assert "..." in rendered


class TestRotation:
    @pytest.mark.asyncio
    async def test_rotates_past_a_spent_key_within_one_request(self):
        p = _provider(dead=["k1"])
        data = await p.generate(_req())
        assert data["predicted_condition"] == "answered-with-k2"
        assert p.keys_tried == ["k1", "k2"]

    @pytest.mark.asyncio
    async def test_a_spent_key_is_not_tried_again_on_the_next_request(self):
        p = _provider(dead=["k1"])
        await p.generate(_req())
        p.keys_tried.clear()
        await p.generate(_req())
        assert p.keys_tried == ["k2"]

    @pytest.mark.asyncio
    async def test_rate_limited_and_rejected_keys_also_rotate(self):
        for error in (RateLimitError, AuthenticationError):
            p = _provider(dead=["k1", "k2"], error=error)
            data = await p.generate(_req())
            assert data["predicted_condition"] == "answered-with-k3"

    @pytest.mark.asyncio
    async def test_raises_once_every_key_is_spent(self):
        p = _provider(dead=["k1", "k2", "k3"])
        with pytest.raises(QuotaExceededError):
            await p.generate(_req())
        assert p.quota_exhausted() is True

    @pytest.mark.asyncio
    async def test_a_failure_unrelated_to_the_key_does_not_burn_the_pool(self):
        """A timeout says nothing about the key's quota. Rotating on it
        would spend every key on what is probably a slow network."""
        p = _provider(dead=["k1"], error=TimeoutError_)
        with pytest.raises(TimeoutError_):
            await p.generate(_req())
        assert p.keys_tried == ["k1"]
        assert p.key_pool.available_count() == 3

    @pytest.mark.asyncio
    async def test_a_user_supplied_key_is_used_instead_of_the_pool(self):
        p = _provider()
        data = await p.generate(_req(user_api_key="mine"))
        assert data["predicted_condition"] == "answered-with-mine"
        assert p.keys_tried == ["mine"]

    @pytest.mark.asyncio
    async def test_a_user_key_works_even_when_every_server_key_is_spent(self):
        """The whole point of asking the user for a key."""
        p = _provider(dead=["k1", "k2", "k3"])
        with pytest.raises(QuotaExceededError):
            await p.generate(_req())
        assert p.quota_exhausted() is True

        p.keys_tried.clear()
        data = await p.generate(_req(user_api_key="mine"))
        assert data["predicted_condition"] == "answered-with-mine"

    @pytest.mark.asyncio
    async def test_a_bad_user_key_does_not_poison_the_server_pool(self):
        p = _provider(dead=["mine"])
        with pytest.raises(QuotaExceededError):
            await p.generate(_req(user_api_key="mine"))
        assert p.key_pool.available_count() == 3


class TestQuotaSignal:
    """The apps only offer the "paste your own key" prompt when the server
    genuinely ran out — never when it is simply misconfigured."""

    @pytest.mark.asyncio
    async def test_flag_is_set_when_the_pool_is_spent(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,mock")
        p = _provider(dead=["k1", "k2", "k3"])
        manager = AIManager(providers={"gemini": p, "mock": MockProvider()})

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.used_mock is True
        assert outcome.quota_exhausted is True

    @pytest.mark.asyncio
    async def test_flag_is_not_set_when_no_provider_is_configured(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,mock")
        p = RotatingProvider(key_pool=KeyPool.from_keys("gemini", []))
        manager = AIManager(providers={"gemini": p, "mock": MockProvider()})

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.used_mock is True
        assert outcome.quota_exhausted is False

    @pytest.mark.asyncio
    async def test_flag_is_not_set_when_a_real_provider_answers(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,mock")
        manager = AIManager(providers={"gemini": _provider(), "mock": MockProvider()})

        outcome = await manager.run(AITask.TRIAGE, prompt="p")

        assert outcome.used_mock is False
        assert outcome.quota_exhausted is False

    @pytest.mark.asyncio
    async def test_a_user_key_bypasses_the_circuit_breaker(self, monkeypatch):
        """Once the breaker marks a provider unhealthy it is skipped
        entirely — which would make a user's own key do nothing."""
        monkeypatch.setenv("AI_PROVIDER_PRIORITY", "gemini,mock")
        p = _provider(dead=["k1", "k2", "k3"])
        manager = AIManager(providers={"gemini": p, "mock": MockProvider()})

        await manager.run(AITask.TRIAGE, prompt="p")
        assert p.is_available() is False

        p.keys_tried.clear()
        outcome = await manager.run(AITask.TRIAGE, prompt="p", user_api_key="mine")

        assert outcome.provider_used == "gemini"
        assert outcome.used_mock is False
        assert p.keys_tried == ["mine"]


class TestUnconfiguredProvider:
    @pytest.mark.asyncio
    async def test_rotation_refuses_when_there_is_nothing_to_try(self):
        p = RotatingProvider(key_pool=KeyPool.from_keys("gemini", []))
        with pytest.raises(ProviderUnavailableError):
            await p.generate(_req())
