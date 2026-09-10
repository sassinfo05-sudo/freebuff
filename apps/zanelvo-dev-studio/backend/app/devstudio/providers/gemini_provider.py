"""Real GeminiProvider, via Google's unified `google-genai` SDK. OPTIONAL runtime dependency (see
backend/requirements-devstudio.txt) — imported lazily so the app boots without it installed.

Model list verified against Google's own current pricing docs (ai.google.dev/gemini-api/docs/pricing,
Sept 2026). Used specifically for the Design agent: Gemini's multimodal + large-context strength is
the genuine, task-specific reason (screenshots, reference images, design language), not a general
capability claim over Anthropic — see the commit that added this file and CLAUDE.md.

Classification note (CLAUDE.md evidence rules): "Live but requires external credentials" until
GEMINI_API_KEY (or a stored Dev Studio secret) is configured — calling it without one raises
ProviderNotConfigured rather than returning fake output.
"""
from __future__ import annotations

import time
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import LLMProvider, LLMResult, LLMUsage, ModelInfo, ProviderNotConfigured

_MODELS = [
    ModelInfo(id="gemini-3.1-pro-preview", provider="gemini", label="Gemini 3.1 Pro Preview",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=1_000_000, notes="Flagship — strongest multimodal/vision reasoning."),
    ModelInfo(id="gemini-3.6-flash", provider="gemini", label="Gemini 3.6 Flash",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=1_000_000, notes="Balanced cost/performance."),
    ModelInfo(id="gemini-3.5-flash-lite", provider="gemini", label="Gemini 3.5 Flash-Lite",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=1_000_000),
    ModelInfo(id="gemini-3.1-flash-lite", provider="gemini", label="Gemini 3.1 Flash-Lite",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=1_000_000, notes="Cheapest Gemini model."),
]

_THINKING_BUDGET = {"low": 1024, "medium": 8192, "high": 24576}


def _sdk():
    try:
        from google import genai
        from google.genai import types
        return genai, types
    except ImportError as e:  # noqa: BLE001
        raise ProviderNotConfigured(
            "The 'google-genai' package is not installed in this environment. Install it via: "
            "pip install -r requirements-devstudio.txt"
        ) from e


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str]):
        self._api_key = api_key

    def _client(self):
        if not self._api_key:
            raise ProviderNotConfigured(
                "GEMINI_API_KEY is not configured. Set it in the environment or store it via "
                "Dev Studio Settings > Secrets (POST /api/devstudio/settings/secrets)."
            )
        genai, _types = _sdk()
        return genai.Client(api_key=self._api_key)

    def list_models(self) -> List[ModelInfo]:
        return list(_MODELS)

    def _usage_from_response(self, resp, duration_ms: int) -> LLMUsage:
        u = getattr(resp, "usage_metadata", None)
        return LLMUsage(
            input_tokens=getattr(u, "prompt_token_count", 0) or 0,
            output_tokens=getattr(u, "candidates_token_count", 0) or 0,
            cache_tokens=getattr(u, "cached_content_token_count", 0) or 0,
            cost_usd=None,  # not returned by the API; UsageTracker leaves it null rather than guess
            duration_ms=duration_ms,
        )

    def _config(self, types, *, system: str, max_tokens: int, temperature: Optional[float] = None,
                json_mode: bool = False, reasoning_level: Optional[str] = None, model: str = ""):
        kwargs: Dict[str, Any] = dict(system_instruction=system, max_output_tokens=max_tokens)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_mime_type"] = "application/json"
        if reasoning_level and self.supports_reasoning_levels(model):
            kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=_THINKING_BUDGET.get(reasoning_level, 8192))
        return types.GenerateContentConfig(**kwargs)

    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult:
        client = self._client()
        _genai, types = _sdk()
        t0 = time.monotonic()
        resp = await client.aio.models.generate_content(
            model=model, contents=prompt,
            config=self._config(types, system=system, max_tokens=max_tokens, temperature=temperature,
                                 reasoning_level=reasoning_level, model=model),
        )
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=resp.text or "", usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def generate_structured(self, *, system: str, prompt: str, model: str,
                                   json_schema: Optional[Dict[str, Any]] = None,
                                   max_tokens: int = 4096) -> LLMResult:
        client = self._client()
        _genai, types = _sdk()
        t0 = time.monotonic()
        strict_system = system + "\n\nRespond with ONLY a single valid JSON object/array."
        if json_schema:
            strict_system += f"\n\nThe JSON MUST conform to this schema:\n{json_schema}"
        resp = await client.aio.models.generate_content(
            model=model, contents=prompt,
            config=self._config(types, system=strict_system, max_tokens=max_tokens, temperature=0.0,
                                 json_mode=True),
        )
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=resp.text or "", usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def generate_with_vision(self, *, system: str, prompt: str, model: str,
                                    images_b64: List[str], max_tokens: int = 4096) -> LLMResult:
        if not self.supports_vision(model):
            raise ProviderNotConfigured(f"Model {model} does not support vision input")
        import base64
        client = self._client()
        _genai, types = _sdk()
        t0 = time.monotonic()
        parts: List[Any] = [types.Part.from_text(text=prompt)]
        for img in images_b64:
            parts.append(types.Part.from_bytes(data=base64.b64decode(img), mime_type="image/png"))
        resp = await client.aio.models.generate_content(
            model=model, contents=parts,
            config=self._config(types, system=system, max_tokens=max_tokens),
        )
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=resp.text or "", usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._client()
        _genai, types = _sdk()
        stream = await client.aio.models.generate_content_stream(
            model=model, contents=prompt,
            config=self._config(types, system=system, max_tokens=max_tokens),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text
