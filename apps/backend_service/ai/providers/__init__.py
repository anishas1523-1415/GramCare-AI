"""Provider registry.

Adding a new provider (requirement #10) means: (1) write a new
`ai/providers/<name>.py` implementing BaseAIProvider, (2) add one line to
`PROVIDER_CLASSES` below. Nothing in `ai/manager.py` needs to change — it
iterates this registry generically.
"""
from .anthropic_provider import AnthropicProvider
from .gemini import GeminiProvider
from .groq_provider import GroqProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider

#: name (as used in AI_PROVIDER_PRIORITY strings) -> provider class.
PROVIDER_CLASSES = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "anthropic": AnthropicProvider,
    "mock": MockProvider,
}

__all__ = [
    "PROVIDER_CLASSES",
    "AnthropicProvider",
    "GeminiProvider",
    "GroqProvider",
    "MockProvider",
    "OpenAIProvider",
]
