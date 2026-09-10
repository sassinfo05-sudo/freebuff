"""Real OpenAIProvider (Chat Completions API). `openai` is an OPTIONAL runtime dependency (see
backend/requirements-devstudio.txt) — imported lazily so the app boots without it installed.

Model list verified against OpenAI's own current pricing page (developers.openai.com/api/docs/pricing,
Sept 2026) rather than assumed — see docs/EMERGENT_INTEGRATION_HANDOFF.md-adjacent reasoning in the
commit that added this file for why OpenAI is used specifically for the Reviewer role (an independent
second opinion from a different lab, not a capability claim over Anthropic for coding tasks).

Classification note (CLAUDE.md evidence rules): "Live but requires external credentials" until
OPENAI_API_KEY (or a stored Dev Studio secret) is configured — calling it without one raises
ProviderNotConfigured rather than returning fake output.
"""
from __future__ import annotations

import time
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import LLMProvider, LLMResult, LLMUsage, ModelInfo, ProviderNotConfigured

_MODELS = [
    ModelInfo(id="gpt-6-astra", provider="openai", label="GPT-6 Astra",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=400_000, notes="Newest OpenAI flagship (Sept 2026)."),
    ModelInfo(id="gpt-5.6-sol", provider="openai", label="GPT-5.6 Sol",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=400_000),
    ModelInfo(id="gpt-5.6-terra", provider="openai", label="GPT-5.6 Terra",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=256_000, notes="Balanced cost/performance mid-tier."),
    ModelInfo(id="gpt-5.6-luna", provider="openai", label="GPT-5.6 Luna",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=128_000, notes="Budget tier."),
    ModelInfo(id="gpt-5-nano", provider="openai", label="GPT-5 Nano",
              supports_tools=True, supports_vision=False, supports_reasoning_levels=False,
              context_window=128_000, notes="Cheapest OpenAI model."),
    ModelInfo(id="gpt-5.3-codex", provider="openai", label="GPT-5.3 Codex",
              supports_tools=True, supports_vision=False, supports_reasoning_levels=True,
              context_window=256_000, notes="Coding-specialized."),
]

_REASONING_EFFORT = {"low": "low", "medium": "medium", "high": "high"}


def _sdk():
    try:
        import openai  # noqa: F401
        return openai
    except ImportError as e:  # noqa: BLE001
        raise ProviderNotConfigured(
            "The 'openai' package is not installed in this environment. Install it via: "
            "pip install -r requirements-devstudio.txt"
        ) from e


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str]):
        self._api_key = api_key

    def _client(self):
        if not self._api_key:
            raise ProviderNotConfigured(
                "OPENAI_API_KEY is not configured. Set it in the environment or store it via "
                "Dev Studio Settings > Secrets (POST /api/devstudio/settings/secrets)."
            )
        openai = _sdk()
        return openai.AsyncOpenAI(api_key=self._api_key)

    def list_models(self) -> List[ModelInfo]:
        return list(_MODELS)

    def _usage_from_response(self, resp, duration_ms: int) -> LLMUsage:
        u = getattr(resp, "usage", None)
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        return LLMUsage(
            input_tokens=getattr(u, "prompt_tokens", 0) or 0,
            output_tokens=getattr(u, "completion_tokens", 0) or 0,
            cache_tokens=cached,
            cost_usd=None,  # not returned by the API; UsageTracker leaves it null rather than guess
            duration_ms=duration_ms,
        )

    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult:
        client = self._client()
        t0 = time.monotonic()
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
            temperature=temperature,
        )
        if reasoning_level and self.supports_reasoning_levels(model):
            kwargs["reasoning_effort"] = _REASONING_EFFORT.get(reasoning_level, "medium")
        resp = await client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=text, usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def generate_structured(self, *, system: str, prompt: str, model: str,
                                   json_schema: Optional[Dict[str, Any]] = None,
                                   max_tokens: int = 4096) -> LLMResult:
        client = self._client()
        t0 = time.monotonic()
        strict_system = system + "\n\nRespond with ONLY a single valid JSON object/array."
        if json_schema:
            strict_system += f"\n\nThe JSON MUST conform to this schema:\n{json_schema}"
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": strict_system}, {"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens, temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or ""
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=text, usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def generate_with_vision(self, *, system: str, prompt: str, model: str,
                                    images_b64: List[str], max_tokens: int = 4096) -> LLMResult:
        if not self.supports_vision(model):
            raise ProviderNotConfigured(f"Model {model} does not support vision input")
        client = self._client()
        t0 = time.monotonic()
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images_b64:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            max_completion_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=text, usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._client()
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
