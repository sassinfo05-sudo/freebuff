"""ModelRegistry — the one place that knows which LLMProvider classes exist and how to build them.

Deliberately provider-independent: adding a new vendor means adding one entry to `_PROVIDER_CLASSES`
and one `ModelInfo` list; nothing in agents/ or services/ changes.

Preset design (ECONOMICAL/BALANCED/MAX_QUALITY): coding-heavy roles (analyst, planner, frontend,
backend, integration, supervisor) stay on Anthropic across all three tiers — Claude has the most
consistently-reported edge on agentic coding/tool-use benchmarks, so using anything else there
would be diversity for its own sake, not a real improvement. Two roles genuinely diverge:

- Design uses Gemini: it works with screenshots, reference images, and design language — Gemini's
  multimodal + very large context window (1M tokens) is a real, task-specific advantage there, not
  a general capability claim over Anthropic.
- Reviewer uses OpenAI as primary (Anthropic as fallback): an independent second opinion from a
  different lab than the implementer reduces correlated blind spots — the same reason a human
  reviewer shouldn't be the PR's own author. This is an architectural choice, not a claim that
  OpenAI reviews code better than Claude does.

Model names/prices were checked against each vendor's own current pricing docs (Sept 2026) rather
than assumed — see the commit that added the OpenAI/Gemini providers.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ModelInfo
from .emergent_provider import EmergentUniversalKeyProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

_PROVIDER_CLASSES: Dict[str, Type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "emergent": EmergentUniversalKeyProvider,
}

_ANTHROPIC_ECONOMICAL = {"primary_provider": "anthropic", "primary_model": "claude-haiku-4-5",
                          "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"}
_ANTHROPIC_BALANCED = {"primary_provider": "anthropic", "primary_model": "claude-sonnet-5",
                        "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"}
_ANTHROPIC_MAX = {"primary_provider": "anthropic", "primary_model": "claude-opus-5",
                   "fallback_provider": "anthropic", "fallback_model": "claude-sonnet-5"}

# Global presets. Each maps agent role -> (primary_provider, primary_model, fallback_provider,
# fallback_model). Roles not listed fall back to the tier's "default" entry.
MODEL_PRESETS: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {
    "ECONOMICAL": {
        "default": _ANTHROPIC_ECONOMICAL,
        "supervisor": _ANTHROPIC_BALANCED,  # orchestration judgment is worth one tier up even here
        "design": {"primary_provider": "gemini", "primary_model": "gemini-3.1-flash-lite",
                   "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"},
        "reviewer": _ANTHROPIC_ECONOMICAL,  # cross-provider review is a quality spend, not a
                                              # cost-tier default — kept same-provider here
    },
    "BALANCED": {
        "default": _ANTHROPIC_BALANCED,
        "design": {"primary_provider": "gemini", "primary_model": "gemini-3.1-pro-preview",
                   "fallback_provider": "anthropic", "fallback_model": "claude-sonnet-5"},
        "reviewer": {"primary_provider": "openai", "primary_model": "gpt-5.6-terra",
                     "fallback_provider": "anthropic", "fallback_model": "claude-sonnet-5"},
    },
    "MAX_QUALITY": {
        "default": _ANTHROPIC_MAX,
        "design": {"primary_provider": "gemini", "primary_model": "gemini-3.1-pro-preview",
                   "fallback_provider": "anthropic", "fallback_model": "claude-opus-5"},
        "reviewer": {"primary_provider": "openai", "primary_model": "gpt-6-astra",
                     "fallback_provider": "anthropic", "fallback_model": "claude-opus-5"},
    },
}


def preset_for_role(preset: str, role: str) -> Dict[str, Optional[str]]:
    p = MODEL_PRESETS.get(preset, MODEL_PRESETS["BALANCED"])
    return p.get(role, p["default"])


class ModelRegistry:
    """Live registry of instantiated providers for one request/task run. Instantiate once per
    orchestration run (providers are cheap; API keys are resolved once via SettingsService)."""

    def __init__(self, api_keys: Dict[str, Optional[str]]):
        self._api_keys = api_keys
        self._instances: Dict[str, LLMProvider] = {}

    def get(self, provider_name: str) -> LLMProvider:
        if provider_name not in self._instances:
            cls = _PROVIDER_CLASSES.get(provider_name)
            if cls is None:
                raise ValueError(f"Unknown provider: {provider_name}")
            self._instances[provider_name] = cls(self._api_keys.get(provider_name))
        return self._instances[provider_name]

    def list_all_models(self) -> List[ModelInfo]:
        out: List[ModelInfo] = []
        for name in _PROVIDER_CLASSES:
            try:
                out.extend(self.get(name).list_models())
            except Exception:  # noqa: BLE001 — a misconfigured provider just contributes no models
                continue
        return out


def known_provider_names() -> List[str]:
    return list(_PROVIDER_CLASSES)
