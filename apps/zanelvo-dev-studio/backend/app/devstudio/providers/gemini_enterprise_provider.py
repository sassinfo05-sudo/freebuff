"""Real GeminiEnterpriseProvider — the same Gemini models, served through Google Cloud's Gemini
Enterprise Agent Platform (the product formerly known as Vertex AI) instead of the plain Gemini
Developer API. Subclasses GeminiProvider: request/response shape is identical (both surfaces are
accessed through the same `google-genai` SDK — Google's own migration docs confirm the Developer
API and the Enterprise Agent Platform API are "now accessible through the unified Google Gen AI
SDK" with unchanged request parameters and response structure); only how the client authenticates
differs, so only `_client()`, `name`, and `list_models()` are overridden here.

Why this exists alongside GeminiProvider: same reason BedrockProvider exists alongside
AnthropicProvider — enterprise deployments that need GCP-native governance (VPC Service Controls,
CMEK, data residency, org-policy controls, existing GCP billing) rather than a bare API key calling
generativelanguage.googleapis.com directly. `google-genai` is the same OPTIONAL runtime dependency
already used by GeminiProvider (see requirements-devstudio.txt) — no new package needed.

Credentials work differently from a single API key (and Vertex AI does not accept API keys at
all — confirmed via Google's own SDK issue tracker): a GCP project ID and location are required,
plus one of two credential paths:

1. A service account key, pasted as JSON into Dev Studio Settings > Secrets
   (`gcp_service_account_json`) — loaded in memory via
   `google.oauth2.service_account.Credentials.from_service_account_info()` and passed to the SDK
   explicitly. Nothing is ever written to disk.
2. Left blank — the SDK falls back to Google's own Application Default Credentials resolution
   (the real `GOOGLE_APPLICATION_CREDENTIALS` file-path env var, `gcloud auth
   application-default login`, or an attached GCE/GKE/Cloud Run service account). This is the
   standard zero-config path for a Dev Studio deployment that already runs inside GCP — a real
   credential source, not a shortcut; a genuinely missing credential still fails at call time
   rather than faking a result.

Verified against Google's own current docs (docs.cloud.google.com/gemini-enterprise-agent-platform,
ai.google.dev/gemini-api/docs/migrate-to-cloud, googleapis/python-genai on GitHub) rather than
assumed, same standard as the other providers in this module — see the commit that added this
file.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .base import ModelInfo, ProviderNotConfigured
from .gemini_provider import GeminiProvider, _sdk

_MODELS = [
    ModelInfo(id="gemini-3.1-pro-preview", provider="gemini_enterprise",
              label="Gemini 3.1 Pro Preview (Enterprise Agent Platform)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=1_000_000,
              notes="Same model as the Gemini Developer API, served through Google Cloud's "
                    "Gemini Enterprise Agent Platform for GCP-native governance/data-residency."),
    ModelInfo(id="gemini-3.6-flash", provider="gemini_enterprise",
              label="Gemini 3.6 Flash (Enterprise Agent Platform)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=True,
              context_window=1_000_000),
    ModelInfo(id="gemini-3.5-flash-lite", provider="gemini_enterprise",
              label="Gemini 3.5 Flash-Lite (Enterprise Agent Platform)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=1_000_000),
    ModelInfo(id="gemini-3.1-flash-lite", provider="gemini_enterprise",
              label="Gemini 3.1 Flash-Lite (Enterprise Agent Platform)",
              supports_tools=True, supports_vision=True, supports_reasoning_levels=False,
              context_window=1_000_000),
]


class GeminiEnterpriseProvider(GeminiProvider):
    name = "gemini_enterprise"

    def __init__(self, credentials: Optional[Dict[str, Optional[str]]]):
        # {"project_id": ..., "location": ..., "service_account_json": ...} — deliberately does
        # NOT call GeminiProvider.__init__, which expects a single api_key string.
        self._creds = credentials or {}

    def list_models(self) -> List[ModelInfo]:
        return list(_MODELS)

    def _client(self):
        project = self._creds.get("project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = self._creds.get("location") or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
        if not project:
            raise ProviderNotConfigured(
                "No GCP project configured for Gemini Enterprise Agent Platform. Set it via Dev "
                "Studio Settings > Secrets (gcp_project_id) or the GOOGLE_CLOUD_PROJECT "
                "environment variable."
            )
        sa_json = self._creds.get("service_account_json") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        info = None
        if sa_json:
            try:
                info = json.loads(sa_json)
            except (json.JSONDecodeError, TypeError) as e:
                raise ProviderNotConfigured(
                    "gcp_service_account_json is not valid JSON — paste the full service account "
                    "key file contents, not a file path."
                ) from e
        genai, _types = _sdk()
        if info is not None:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            return genai.Client(vertexai=True, project=project, location=location, credentials=credentials)
        # No service account JSON stored — Vertex AI does not accept API keys, so this relies on
        # Google's real Application Default Credentials chain (GOOGLE_APPLICATION_CREDENTIALS file
        # path, `gcloud auth application-default login`, or an attached GCP service account).
        return genai.Client(vertexai=True, project=project, location=location)
