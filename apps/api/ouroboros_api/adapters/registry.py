"""Singleton provider + adapter registries with the default implementations registered."""

from __future__ import annotations

from .agents.anthropic_api import AnthropicAgentAdapter
from .agents.builtin import BuiltinAgentAdapter
from .agents.gh_copilot_cli import GhCopilotCliAdapter
from .agents.github_models_api import GithubModelsAgentAdapter
from .agents.ollama_api import OllamaAgentAdapter
from .agents.opencode_cli import OpencodeCliAdapter
from .base import AdapterRegistry, ProviderRegistry
from .providers.anthropic import AnthropicProvider
from .providers.github_models import GithubModelsProvider
from .providers.ollama import OllamaProvider
from .providers.openai_compatible import OpenAICompatibleProvider

_provider_registry = ProviderRegistry()
_provider_registry.register(OllamaProvider())
_provider_registry.register(AnthropicProvider())
_provider_registry.register(GithubModelsProvider())
_provider_registry.register(OpenAICompatibleProvider())


_adapter_registry = AdapterRegistry()
_adapter_registry.register(BuiltinAgentAdapter())
_adapter_registry.register(OllamaAgentAdapter(_provider_registry))
_adapter_registry.register(AnthropicAgentAdapter(_provider_registry))
_adapter_registry.register(GithubModelsAgentAdapter(_provider_registry))
_adapter_registry.register(OpencodeCliAdapter())
_adapter_registry.register(GhCopilotCliAdapter())


def providers() -> ProviderRegistry:
    return _provider_registry


def adapters() -> AdapterRegistry:
    return _adapter_registry
