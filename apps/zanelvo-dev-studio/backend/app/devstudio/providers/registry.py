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

Within Anthropic, MAX_QUALITY further splits Fable 5.1 vs Opus 5 by role rather than picking one
model for everything:

- Supervisor, Repository Analyst, Planner, and Frontend use Fable 5.1 — it's Anthropic's newest
  flagship, built for long-running agentic problem-solving and self-recovery, and beats Opus 5 on
  most benchmarks while using far fewer output tokens. Its weak spot is lower single-shot (pass@1)
  accuracy than Opus, which matters less for orchestration/analysis/planning/UI work, where a
  wrong first attempt gets caught and retried rather than shipped.
- Backend and Integration stay on Opus 5. Fable carries safety guardrails around cybersecurity/
  biology content that can trigger on legitimate security-adjacent code (auth flows, crypto,
  sandboxing, permission checks) — exactly what these two roles write routinely — and silently
  falls back to a weaker model (Opus 4.8) when it does. Opus 5 has no such block risk and the
  highest pass@1 of the lineup, which is worth more than Fable's efficiency gains for code that
  guards tenant boundaries and secrets.
- Design and Reviewer are unaffected by this split — they were already on Gemini/OpenAI.

Model names/prices were checked against each vendor's own current pricing docs (Sept 2026) rather
than assumed — see the commit that added the OpenAI/Gemini providers.

Credential paths (Settings > Secrets, or the equivalent env vars): native per-vendor API keys
(anthropic/openai/gemini — one key each), Amazon Bedrock (an AWS access key/secret pair + region,
or the default AWS credential chain if no key pair is stored — see bedrock_provider.py), Google's
Gemini Enterprise Agent Platform (a GCP project/location + optional service account JSON, or
Application Default Credentials if none is stored — see gemini_enterprise_provider.py), and the
Emergent Universal Key (one key for GPT/Claude/Gemini via Emergent's proxy — real implementation,
see emergent_provider.py; its optional dependency lives in requirements-emergent.txt, not
requirements-devstudio.txt, due to a pinned-openai-version conflict documented there). None of the
three presets
route through Bedrock, Gemini Enterprise, or Emergent by default; all three are available as an
explicit per-role override (Settings > Agents > pick a role > choose provider) for deployments
that need them, without changing what ships to everyone else.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AgentConfiguration

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ModelInfo
from .bedrock_provider import BedrockProvider
from .emergent_provider import EmergentUniversalKeyProvider
from .gemini_enterprise_provider import GeminiEnterpriseProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

_PROVIDER_CLASSES: Dict[str, Type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "gemini_enterprise": GeminiEnterpriseProvider,
    "bedrock": BedrockProvider,
    "emergent": EmergentUniversalKeyProvider,
}

# Every preset routes through the Emergent Universal Key (provider "emergent") — one key that
# serves the OpenAI, Anthropic AND Gemini families (see emergent_provider._CATALOG). The three
# presets therefore never CHANGE the provider (it's always "emergent", with automatic fallback to
# any other key that happens to be configured — see auto_attempts); they only pick the best MODEL
# for each role. The picks are deliberately cross-family, matched to each role's real strength
# rather than defaulting everything to one vendor:
#   - Gemini (huge multimodal context) -> design, vision, repository_analyst
#   - GPT (strong independent reasoning) -> planner, qa, reviewer
#   - Claude (agentic coding / tool use) -> supervisor, frontend, backend, integration
# Model ids below are the exact Universal-Key catalog ids from emergent_provider._CATALOG.

# OpenAI family
_GPT_MINI = "gpt-5.4-mini"
_GPT_GEN = "gpt-5.4"
_GPT_BAL = "gpt-5.6-terra"
_GPT_MAX = "gpt-6-astra"
# Anthropic family
_SONNET_46 = "claude-sonnet-4-6"
_SONNET_5 = "claude-sonnet-5"
_OPUS_5 = "claude-opus-5"
_FABLE = "claude-fable-5-1"
# Gemini family
_GEM_PRO = "gemini-3.1-pro-preview"
_GEM_FLASH = "gemini-3-flash-preview"
_GEM_FLASH_25 = "gemini-2.5-flash"


def _em(primary_model: str, fallback_model: str) -> Dict[str, Optional[str]]:
    """A preset entry — provider is always Emergent (the Universal Key); only the model varies."""
    return {"primary_provider": "emergent", "primary_model": primary_model,
            "fallback_provider": "emergent", "fallback_model": fallback_model}


# Global presets. Each maps agent role -> (primary_provider, primary_model, fallback_provider,
# fallback_model). Roles not listed fall back to the tier's "default" entry. primary_provider is
# always "emergent" — the preset buttons change the model, never the provider.
MODEL_PRESETS: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {
    "ECONOMICAL": {
        "default": _em(_GPT_MINI, _SONNET_46),
        "supervisor": _em(_SONNET_46, _GPT_BAL),
        "repository_analyst": _em(_GEM_FLASH_25, _GEM_PRO),   # 1M-ctx repo scan, cheap
        "planner": _em(_GPT_GEN, _SONNET_46),
        "design": _em(_GEM_FLASH_25, _GEM_FLASH),
        "vision": _em(_GEM_FLASH_25, _GEM_PRO),
        "frontend": _em(_SONNET_46, _GPT_MINI),
        "backend": _em(_SONNET_46, _GPT_MINI),
        "integration": _em(_SONNET_46, _GPT_MINI),
        "qa": _em(_GPT_MINI, _SONNET_46),
        "reviewer": _em(_GPT_MINI, _SONNET_46),               # cross-family review
        "git": _em(_GEM_FLASH, _GPT_MINI),
    },
    "BALANCED": {
        "default": _em(_SONNET_5, _GPT_BAL),
        "supervisor": _em(_FABLE, _SONNET_5),
        "repository_analyst": _em(_GEM_PRO, _SONNET_5),
        "planner": _em(_GPT_BAL, _SONNET_5),
        "design": _em(_GEM_PRO, _SONNET_5),
        "vision": _em(_GEM_PRO, _SONNET_5),
        "frontend": _em(_SONNET_5, _GPT_BAL),
        "backend": _em(_SONNET_5, _OPUS_5),
        "integration": _em(_SONNET_5, _OPUS_5),
        "qa": _em(_GPT_BAL, _SONNET_5),
        "reviewer": _em(_GPT_BAL, _SONNET_5),
        "git": _em(_GEM_FLASH, _SONNET_5),
    },
    "MAX_QUALITY": {
        "default": _em(_OPUS_5, _FABLE),                       # backend/integration/qa/git etc.
        "supervisor": _em(_FABLE, _OPUS_5),
        "repository_analyst": _em(_GEM_PRO, _OPUS_5),
        "planner": _em(_GPT_MAX, _FABLE),
        "design": _em(_GEM_PRO, _OPUS_5),
        "vision": _em(_GEM_PRO, _OPUS_5),
        "frontend": _em(_FABLE, _OPUS_5),
        "backend": _em(_OPUS_5, _FABLE),
        "integration": _em(_OPUS_5, _FABLE),
        "qa": _em(_GPT_MAX, _OPUS_5),
        "reviewer": _em(_GPT_MAX, _OPUS_5),
        "git": _em(_GPT_BAL, _SONNET_5),
    },
}


def preset_for_role(preset: str, role: str) -> Dict[str, Optional[str]]:
    p = MODEL_PRESETS.get(preset, MODEL_PRESETS["BALANCED"])
    return p.get(role, p["default"])


# A reasonable, real, currently-served model for each provider — used by auto_attempts() below for
# any configured provider that isn't already the role's own curated primary/fallback choice (which
# is used instead when it applies, so curation from MODEL_PRESETS is never discarded, just extended
# to "and also try whatever else you've configured a key for").
_DEFAULT_MODEL_BY_PROVIDER: Dict[str, str] = {
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-3.1-pro-preview",
    "openai": "gpt-5.6-terra",
    "bedrock": "anthropic.claude-sonnet-5-v1:0",
    "gemini_enterprise": "gemini-3.1-pro-preview",
    "emergent": "claude-sonnet-5",
}

# Global cascade order for the automatic-fallback path. Emergent (the Universal Key) is ALWAYS the
# main provider — it's the one key that serves every model family — followed by any native
# per-vendor key, then the cloud-account providers, if a founder happens to have those configured
# too. auto_attempts() below always tries Emergent first and only falls through to these when a
# call to Emergent itself can't be made or fails.
_AUTO_FALLBACK_ORDER = ["emergent", "anthropic", "gemini", "openai", "bedrock", "gemini_enterprise"]


def auto_attempts(config: "AgentConfiguration", registry: "ModelRegistry") -> List[Tuple[str, str]]:
    """Builds the primary->fallback->... attempt list for AgentConfiguration.auto_provider=True.

    Emergent is always the main attempt (using this role's own curated model, so the preset's
    per-role model choice is still honored even in auto mode), then every OTHER provider that
    actually has a real credential configured (registry.is_configured), in a fixed order. Returns
    [] if no provider has a credential at all — the caller turns that into a clear
    "requires_credentials" failure rather than trying anything."""
    attempts: List[Tuple[str, str]] = []
    primary = config.primary_provider or "emergent"
    # The role's own curated model runs first on its primary provider (Emergent for every preset).
    if registry.is_configured(primary) and config.primary_model:
        attempts.append((primary, config.primary_model))
    for name in _AUTO_FALLBACK_ORDER:
        if name == primary or not registry.is_configured(name):
            continue
        model = _DEFAULT_MODEL_BY_PROVIDER.get(name, "")
        if model:
            attempts.append((name, model))
    return attempts


class ModelRegistry:
    """Live registry of instantiated providers for one request/task run. Instantiate once per
    orchestration run (providers are cheap; API keys are resolved once via SettingsService).

    `api_keys` values are usually a single API key string, except "bedrock" — Bedrock uses the
    AWS credential model (access key/secret pair + region), so its value is a small dict instead;
    see BedrockProvider.__init__."""

    def __init__(self, api_keys: Dict[str, Any]):
        self._api_keys = api_keys
        self._instances: Dict[str, LLMProvider] = {}

    def get(self, provider_name: str) -> LLMProvider:
        if provider_name not in self._instances:
            cls = _PROVIDER_CLASSES.get(provider_name)
            if cls is None:
                raise ValueError(f"Unknown provider: {provider_name}")
            self._instances[provider_name] = cls(self._api_keys.get(provider_name))
        return self._instances[provider_name]

    def is_configured(self, provider_name: str) -> bool:
        """True only if this provider has a real credential set — never a network call, just the
        same presence check routes.py's /capabilities endpoint already makes per provider. Used by
        auto_attempts() to build a cascade purely from what's actually usable."""
        value = self._api_keys.get(provider_name)
        if provider_name == "bedrock":
            # Key pair is optional (the default AWS credential chain can cover it) — region is the
            # one thing BedrockProvider can't fall back on, so it's the real readiness signal.
            return bool((value or {}).get("region"))
        if provider_name == "gemini_enterprise":
            # Service account JSON is optional (Application Default Credentials can cover it) —
            # project id is the one thing GeminiEnterpriseProvider can't fall back on.
            return bool((value or {}).get("project_id"))
        return bool(value)

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
