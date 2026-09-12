"""PerplexityService — real HTTP call to Perplexity's chat-completions-compatible API
(https://docs.perplexity.ai) for cited web research. Used by the `perplexity_research` built-in
agent tool (see agents/runner.py). httpx is already a core dependency (github_provider.py uses it
the same way) — nothing optional to install here.

Classification note (CLAUDE.md evidence rules): "Live but requires external credentials" until
PERPLEXITY_API_KEY (or the stored `perplexity_api_key` secret) is configured.
"""
from __future__ import annotations

import httpx

_API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityNotConfigured(Exception):
    pass


class PerplexityError(Exception):
    pass


async def research(query: str, api_key: str | None) -> str:
    if not api_key:
        raise PerplexityNotConfigured(
            "Perplexity research requires PERPLEXITY_API_KEY (env) or the stored "
            "perplexity_api_key secret — neither is configured."
        )
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                },
            )
        except httpx.HTTPError as e:
            raise PerplexityError(f"Perplexity request failed: {type(e).__name__}: {e}") from e
    if resp.status_code == 401:
        raise PerplexityNotConfigured("Perplexity rejected the API key (401 Unauthorized).")
    if resp.status_code >= 400:
        raise PerplexityError(f"Perplexity returned {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations") or []
    if citations:
        content += "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations)
    return content
