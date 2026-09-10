"""EmergentUniversalKeyProvider — INTENTIONAL STUB.

Per the Dev Studio build task: "If Emergent Universal Key is unavailable during this
implementation, leave a real interface and provider stub with clear TODO integration boundary,
not fake functionality." This class implements the full LLMProvider surface so it is a drop-in
registry entry, but every method raises ProviderNotImplemented until Emergent wires the actual
Universal Key HTTP client behind it.

See docs/EMERGENT_INTEGRATION_HANDOFF.md for the exact integration boundary: what to replace here
and what request/response shape is expected. The `emergentintegrations` package (Emergent's public
CDN wheel, not on PyPI) is the suggested transport — see the handoff doc for the lazy-import
pattern to follow (the same one used elsewhere in this file for `anthropic`).
"""
from __future__ import annotations

from typing import AsyncIterator, Dict, List, Optional

from .base import LLMProvider, LLMResult, ModelInfo, ProviderNotImplemented

_TODO = (
    "EmergentUniversalKeyProvider is a stub. TODO(Emergent): implement using the Emergent "
    "Universal Key client — see docs/EMERGENT_INTEGRATION_HANDOFF.md for the transport, the "
    "request/response contract, and the lazy-import pattern to follow."
)


class EmergentUniversalKeyProvider(LLMProvider):
    name = "emergent"

    def __init__(self, universal_key: Optional[str] = None):
        self._universal_key = universal_key

    def list_models(self) -> List[ModelInfo]:
        # Model discovery must come from Emergent's Universal Key model list at integration time.
        return []

    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult:
        raise ProviderNotImplemented(_TODO)

    async def generate_structured(self, *, system: str, prompt: str, model: str,
                                   json_schema: Optional[Dict] = None,
                                   max_tokens: int = 4096) -> LLMResult:
        raise ProviderNotImplemented(_TODO)

    async def generate_with_vision(self, *, system: str, prompt: str, model: str,
                                    images_b64: List[str], max_tokens: int = 4096) -> LLMResult:
        raise ProviderNotImplemented(_TODO)

    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]:
        raise ProviderNotImplemented(_TODO)
        yield ""  # pragma: no cover — makes this an async generator; unreachable
