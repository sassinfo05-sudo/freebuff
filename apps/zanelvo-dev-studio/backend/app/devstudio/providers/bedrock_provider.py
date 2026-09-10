"""Real BedrockProvider — the same Claude models, served through Amazon Bedrock instead of
Anthropic's direct API. `boto3` is an OPTIONAL runtime dependency (see
backend/requirements-devstudio.txt) — imported lazily so the app boots without it installed.

Why this exists alongside AnthropicProvider: same model family, different transport/billing/
compliance boundary. Some deployments need requests to stay inside AWS (data residency, existing
AWS billing, Bedrock provisioned throughput, VPC-only egress) rather than calling
api.anthropic.com directly — Bedrock is the AWS-native path to the same models.

Credentials work differently from the single-API-key providers: Bedrock uses the standard AWS
credential model — an access key/secret pair (Dev Studio Settings > Secrets: `aws_access_key_id` /
`aws_secret_access_key`) plus a region (`aws_region`). If no explicit key pair is stored, boto3
falls back to its own default credential chain (env vars, `~/.aws/credentials`, an EC2/ECS/Lambda
IAM role) — a standard AWS pattern, not a shortcut. A region is always required (Bedrock is
region-scoped); a missing-credential failure at call time still surfaces as ProviderNotConfigured
rather than faking a result (see `_invoke`).

Model IDs: AWS assigns Bedrock's per-model ID strings independently of Anthropic's own API model
names, and they can't be verified against a live AWS console from this environment (CLAUDE.md
evidence rules — no reproducible source for this). The IDs below follow AWS's established
`anthropic.<model>-v<major>:<revision>` convention for Opus/Sonnet/Haiku; a wrong ID fails loudly
with a `ValidationException` rather than silently, so this is safe to discover and correct against
the Bedrock console's model catalog for the target region before relying on it in production.
Claude Fable 5.1 is deliberately NOT listed here — there is no confirmed evidence it is available
on Bedrock yet; add it once that is verified rather than assuming parity with the direct API.
"""
from __future__ import annotations

import asyncio
import base64
import threading
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import LLMProvider, LLMResult, LLMUsage, ModelInfo, ProviderNotConfigured

_MODELS = [
    ModelInfo(id="anthropic.claude-opus-5-v1:0", provider="bedrock", label="Claude Opus 5 (Bedrock)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=200_000,
              notes="Same model as the direct Anthropic API, served through AWS Bedrock. Verify "
                    "this exact model ID in the Bedrock console's model catalog for your region "
                    "before relying on it — AWS assigns Bedrock model IDs independently."),
    ModelInfo(id="anthropic.claude-sonnet-5-v1:0", provider="bedrock", label="Claude Sonnet 5 (Bedrock)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=200_000),
    ModelInfo(id="anthropic.claude-haiku-4-5-v1:0", provider="bedrock", label="Claude Haiku 4.5 (Bedrock)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=200_000),
]


def _sdk():
    try:
        import boto3  # noqa: F401
        return boto3
    except ImportError as e:  # noqa: BLE001
        raise ProviderNotConfigured(
            "The 'boto3' package is not installed in this environment. Install it via: "
            "pip install -r requirements-devstudio.txt"
        ) from e


class BedrockProvider(LLMProvider):
    name = "bedrock"

    def __init__(self, credentials: Optional[Dict[str, Optional[str]]]):
        # {"access_key_id": ..., "secret_access_key": ..., "region": ..., "session_token": ...}
        self._creds = credentials or {}

    def _client(self):
        import os
        region = (
            self._creds.get("region")
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
        )
        if not region:
            raise ProviderNotConfigured(
                "No AWS region configured for Bedrock. Set it via Dev Studio Settings > Secrets "
                "(aws_region) or the AWS_REGION/AWS_DEFAULT_REGION environment variable."
            )
        boto3 = _sdk()
        access_key = self._creds.get("access_key_id")
        secret_key = self._creds.get("secret_access_key")
        if access_key and secret_key:
            return boto3.client(
                "bedrock-runtime", region_name=region,
                aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                aws_session_token=self._creds.get("session_token") or None,
            )
        # No explicit key pair stored — let boto3's own default credential chain resolve it
        # (env vars, shared config file, an EC2/ECS/Lambda IAM role). A real AWS-native path, not
        # a fake success: a genuinely missing credential still raises from `_invoke` below.
        return boto3.client("bedrock-runtime", region_name=region)

    def list_models(self) -> List[ModelInfo]:
        return list(_MODELS)

    async def _invoke(self, fn, **kwargs) -> Dict[str, Any]:
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError
        try:
            return await asyncio.to_thread(fn, **kwargs)
        except (NoCredentialsError, PartialCredentialsError) as e:
            raise ProviderNotConfigured(
                "AWS credentials not found for Bedrock. Configure aws_access_key_id / "
                "aws_secret_access_key via Dev Studio Settings > Secrets, or rely on the default "
                "AWS credential chain (env vars, ~/.aws/credentials, an IAM role)."
            ) from e

    def _usage_from_response(self, resp: Dict[str, Any], duration_ms: int) -> LLMUsage:
        u = resp.get("usage") or {}
        return LLMUsage(
            input_tokens=u.get("inputTokens", 0) or 0,
            output_tokens=u.get("outputTokens", 0) or 0,
            cache_tokens=(u.get("cacheReadInputTokens", 0) or 0) + (u.get("cacheWriteInputTokens", 0) or 0),
            cost_usd=None,  # Bedrock responses don't include $ cost; UsageTracker leaves it null
            duration_ms=duration_ms,
        )

    @staticmethod
    def _text_from_message(resp: Dict[str, Any]) -> str:
        blocks = resp.get("output", {}).get("message", {}).get("content", [])
        return "".join(b.get("text", "") for b in blocks if "text" in b)

    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult:
        client = self._client()
        t0 = time.monotonic()
        kwargs: Dict[str, Any] = dict(
            modelId=model,
            system=[{"text": system}] if system else [],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        if reasoning_level and self.supports_reasoning_levels(model):
            budget = {"low": 1024, "medium": 4096, "high": 12000}.get(reasoning_level, 4096)
            kwargs["additionalModelRequestFields"] = {"thinking": {"type": "enabled", "budget_tokens": budget}}
        resp = await self._invoke(client.converse, **kwargs)
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=self._text_from_message(resp), usage=self._usage_from_response(resp, dur),
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
        content: List[Dict[str, Any]] = [{"text": prompt}]
        for img in images_b64:
            content.append({"image": {"format": "png", "source": {"bytes": base64.b64decode(img)}}})
        resp = await self._invoke(
            client.converse, modelId=model,
            system=[{"text": system}] if system else [],
            messages=[{"role": "user", "content": content}],
            inferenceConfig={"maxTokens": max_tokens},
        )
        dur = int((time.monotonic() - t0) * 1000)
        return LLMResult(text=self._text_from_message(resp), usage=self._usage_from_response(resp, dur),
                          model=model, provider=self.name)

    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._client()
        kwargs: Dict[str, Any] = dict(
            modelId=model,
            system=[{"text": system}] if system else [],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens},
        )
        loop = asyncio.get_event_loop()
        queue: "asyncio.Queue[object]" = asyncio.Queue()

        def _run() -> None:
            try:
                resp = client.converse_stream(**kwargs)
                for event in resp["stream"]:
                    delta = event.get("contentBlockDelta", {}).get("delta", {})
                    text = delta.get("text")
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as e:  # noqa: BLE001 — relayed to the consumer, not swallowed
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=_run, daemon=True).start()
        while True:
            item = await queue.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item  # type: ignore[misc]
