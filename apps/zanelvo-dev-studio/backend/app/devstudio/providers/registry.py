"""ModelRegistry — the one place that knows which LLMProvider classes exist and how to build them.

Deliberately provider-independent: adding a new vendor means adding one entry to `_PROVIDER_CLASSES`
and one `ModelInfo` list; nothing in agents/ or services/ changes.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ModelInfo
from .emergent_provider import EmergentUniversalKeyProvider

_PROVIDER_CLASSES: Dict[str, Type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "emergent": EmergentUniversalKeyProvider,
}

# Global presets. Each maps agent role -> (primary_provider, primary_model, fallback_provider,
# fallback_model). Roles not listed fall back to BALANCED's "default" entry.
MODEL_PRESETS: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {
    "ECONOMICAL": {
        "default": {"primary_provider": "anthropic", "primary_model": "claude-haiku-4-5",
                    "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"},
        "supervisor": {"primary_provider": "anthropic", "primary_model": "claude-sonnet-5",
                       "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"},
    },
    "BALANCED": {
        "default": {"primary_provider": "anthropic", "primary_model": "claude-sonnet-5",
                    "fallback_provider": "anthropic", "fallback_model": "claude-haiku-4-5"},
        "reviewer": {"primary_provider": "anthropic", "primary_model": "claude-opus-5",
                     "fallback_provider": "anthropic", "fallback_model": "claude-sonnet-5"},
    },
    "MAX_QUALITY": {
        "default": {"primary_provider": "anthropic", "primary_model": "claude-opus-5",
                    "fallback_provider": "anthropic", "fallback_model": "claude-sonnet-5"},
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
            if provider_name == "emergent":
                self._instances[provider_name] = cls(self._api_keys.get(provider_name))
            else:
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
