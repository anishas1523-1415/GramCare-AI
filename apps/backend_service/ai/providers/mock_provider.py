"""Mock provider — the guaranteed last resort (requirement #12).

Always "configured" and always "available": this provider must never itself
be the reason the application fails to respond. It returns clearly-labeled
fallback data so downstream consumers (and anyone debugging logs/metrics)
can immediately tell a real AI response was NOT produced.
"""
from __future__ import annotations

from ..base import AIRequest, AITask, BaseAIProvider

MOCK_DISCLAIMER_NOTE = "AI Engines unavailable — returning safe fallback data."


class MockProvider(BaseAIProvider):
    name = "mock"

    def __init__(self, **kwargs):
        # No API key needed — always configured. AIManager constructs every
        # provider uniformly via `cls(api_key=<env value>, health_cache_seconds=...)`,
        # so for mock the incoming api_key is always None (see
        # ai/manager.py's `_ENV_KEY_BY_PROVIDER["mock"] = None`). We discard
        # it and force our own "mock" placeholder instead of forwarding the
        # caller's api_key= — passing both would raise
        # "got multiple values for keyword argument 'api_key'".
        kwargs.pop("api_key", None)
        super().__init__(api_key="mock", **kwargs)

    def is_configured(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO}

    def supports_vision(self) -> bool:
        return True  # accepts (and ignores) image input rather than erroring

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return False

    async def generate(self, request: AIRequest) -> dict:
        if request.task == AITask.TRIAGE:
            return {
                "severity_score": 50,
                "predicted_condition": "Unknown (AI Engines Unavailable)",
                "home_remedies": "Rest and stay hydrated.",
                "doctor_recommendation": "Please consult a doctor for a proper evaluation — AI analysis is temporarily unavailable.",
                "recovery_time": "N/A",
                "status": "Warning",
                "confidence_score": 0.0,
                "explanation": MOCK_DISCLAIMER_NOTE,
                "possible_causes": "Not available in fallback mode.",
                "first_aid": "Keep the patient comfortable and hydrated.",
                "side_effects": "",
                "treatment_options": "",
                "untreated_outcome": "",
                "specialist_type": "General Physician",
                "language_detected": "en",
            }

        if request.task == AITask.OCR:
            return {
                "extracted_text": f"[{MOCK_DISCLAIMER_NOTE}]",
                "medicines_parsed": [],
                "confidence": 0.0,
            }

        if request.task == AITask.DOCTOR_SUMMARY:
            return {"summary_text": MOCK_DISCLAIMER_NOTE}

        if request.task == AITask.MEDICINE_INFO:
            return {
                "purpose": MOCK_DISCLAIMER_NOTE,
                "dosage_guidance": "Follow the dosage printed on your prescription or medicine strip.",
                "side_effects": "Not available in fallback mode — ask your pharmacist.",
                "precautions": "",
            }

        return {"note": MOCK_DISCLAIMER_NOTE}
