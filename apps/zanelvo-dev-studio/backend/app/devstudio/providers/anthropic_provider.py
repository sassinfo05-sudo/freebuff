"""Real AnthropicProvider. `anthropic` is an OPTIONAL runtime dependency (see
backend/requirements-devstudio.txt) — imported lazily so the app boots (and its deterministic
tests pass) without it installed.

Classification note (CLAUDE.md evidence rules): this provider is "Live but requires external
credentials" until ANTHROPIC_API_KEY (or a stored Dev Studio secret) is configured — calling it
without one raises ProviderNotConfigured rather than returning fake output.
"""
from __future__ import annotations

import time
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import LLMProvider, LLMResult, LLMUsage, ModelInfo, ProviderNotConfigured

# Known Anthropic models Dev Studio can target. Kept as a static registry (per the spec's
# ModelRegistry requirement) rather than a live discovery call, since Anthropic's Python SDK has
# no `models.list` guaranteed-stable endpoint across all deployments; this list is easy to extend.
_MODELS = [
    ModelInfo(id="claude-fable-5-1", provider="anthropic", label="Claude Fable 5.1",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=200_000,
              notes="Newest flagship, tuned for long-running agentic tasks and self-recovery; "
                    "beats Opus 5 on most benchmarks but has lower single-shot (pass@1) accuracy "
                    "and carries cybersecurity/biology safety guardrails that can block on "
                    "legitimate security-adjacent code (auth, crypto, sandboxing) — kept off "
                    "Backend/Integration for that reason, see registry.py."),
    ModelInfo(id="claude-opus-5", provider="anthropic", label="Claude Opus 5",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=200_000),
    ModelInfo(id="claude-sonnet-5", provider="anthropic", label="Claude Sonnet 5",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=200_000),
    ModelInfo(id="claude-haiku-4-5", provider="anthropic", label="Claude Haiku 4.5",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=200_000),
]


def _sdk():
    try:
        import anthropic  # noqa: F401
        return anthropic
    except ImportError as e:  # noqa: BLE001
        raise ProviderNotConfigured(
            "The 'anthropic' package is not installed in this environment. Install it via: "
            "pip install -r requirements-devstudio.txt"
        ) from e


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str]):
        self._api_key = api_key

    def _client(self):
        if not self._api_key:
            raise ProviderNotConfigured(
                "ANTHROPIC_API_KEY is not configured. Set it in the environment or store it via "
                "Dev Studio Settings > Secrets (POST /api/devstudio/settings/secrets)."
            )
        anthropic = _sdk()
        return anthropic.AsyncAnthropic(api_key=self._api_key)

    def list_models(self) -> List[ModelInfo]:
        return list(_MODELS)

    def _usage_from_response(self, resp, duration_ms: int) -> LLMUsage:
        u = getattr(resp, "usage", None)
        return LLMUsage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_tokens=(getattr(u, "cache_read_input_tokens", 0) or 0)
            + (getattr(u, "cache_creation_input_tokens", 0) or 0),
            cost_usd=None,  # Anthropic responses don't include $ cost; UsageTracker leaves it null
            duration_ms=duration_ms,
        )

    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult:
        client = self._client()
        t0 = time.monotonic()
        kwargs: Dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=[{"role": "user", "content": prompt}],
        )
        if reasoning_level and self.supports_reasoning_levels(model):
            budget = {"low": 1024, "medium": 4096, "high": 12000}.get(reasoning_level, 4096)
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        resp = await client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=text, usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name, raw=None)

    async def generate_structured(self, *, system: str, prompt: str, model: str,
                                   json_schema: Optional[Dict[str, Any]] = None,
                                   max_tokens: int = 4096) -> LLMResult:
        strict_system = (
            system
            + "\n\nRespond with ONLY a single valid JSON object/array. No prose, no markdown "
              "code fences, no explanation before or after the JSON."
        )
        if json_schema:
            strict_system += f"\n\nThe JSON MUST conform to this schema:\n{json_schema}"
        return await self.generate(system=strict_system, prompt=prompt, model=model,
                                    max_tokens=max_tokens, temperature=0.0)

    async def generate_with_vision(self, *, system: str, prompt: str, model: str,
                                    images_b64: List[str], max_tokens: int = 4096) -> LLMResult:
        if not self.supports_vision(model):
            raise ProviderNotConfigured(f"Model {model} does not support vision input")
        client = self._client()
        t0 = time.monotonic()
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img},
            })
        resp = await client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=text, usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._client()
        async with client.messages.stream(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
