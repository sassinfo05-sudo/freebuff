"""Deterministic tests for the multi-provider ModelRegistry, plus BedrockProvider's and
GeminiEnterpriseProvider's pure/sync config-validation paths. No DB/network — mirrors the pattern
in test_devstudio_execution_service.py.
"""
from app.devstudio.providers.base import ProviderNotConfigured
from app.devstudio.providers.bedrock_provider import BedrockProvider
from app.devstudio.providers.gemini_enterprise_provider import GeminiEnterpriseProvider
from app.devstudio.providers.registry import MODEL_PRESETS, known_provider_names, preset_for_role

_CLOUD_ROUTED_PROVIDERS = ("bedrock", "gemini_enterprise", "emergent")


def test_known_provider_names_includes_every_provider():
    names = known_provider_names()
    assert set(names) == {"anthropic", "openai", "gemini", "gemini_enterprise", "bedrock", "emergent"}


def test_cloud_routed_providers_not_used_by_any_preset_by_default():
    # Bedrock/Gemini Enterprise/Emergent are opt-in per-role overrides (Settings > Agents), not
    # preset defaults — nothing in MODEL_PRESETS should silently route through them.
    for preset in MODEL_PRESETS.values():
        for cfg in preset.values():
            assert cfg["primary_provider"] not in _CLOUD_ROUTED_PROVIDERS
            assert cfg["fallback_provider"] not in _CLOUD_ROUTED_PROVIDERS


def test_preset_for_role_unaffected_by_bedrock_addition():
    p = preset_for_role("MAX_QUALITY", "backend")
    assert p["primary_provider"] == "anthropic"
    assert p["primary_model"] == "claude-opus-5"


def test_bedrock_list_models_works_without_any_credentials():
    models = BedrockProvider(None).list_models()
    assert models, "expected a static model list even with no credentials configured"
    assert all(m.provider == "bedrock" for m in models)
    assert all(m.id.startswith("anthropic.") for m in models)


def test_bedrock_does_not_list_fable_without_verified_availability():
    ids = {m.id for m in BedrockProvider(None).list_models()}
    assert not any("fable" in i for i in ids)


def test_bedrock_client_requires_a_region():
    provider = BedrockProvider({"access_key_id": "AKIA_FAKE", "secret_access_key": "fake"})
    try:
        provider._client()
        assert False, "expected ProviderNotConfigured when no region is configured"
    except ProviderNotConfigured as e:
        assert "region" in str(e).lower()


def test_bedrock_client_requires_region_even_with_empty_credentials_dict():
    provider = BedrockProvider({})
    try:
        provider._client()
        assert False, "expected ProviderNotConfigured when no region is configured"
    except ProviderNotConfigured:
        pass


def test_gemini_enterprise_list_models_works_without_any_credentials():
    models = GeminiEnterpriseProvider(None).list_models()
    assert models, "expected a static model list even with no credentials configured"
    assert all(m.provider == "gemini_enterprise" for m in models)
    assert all(m.id.startswith("gemini-") for m in models)


def test_gemini_enterprise_client_requires_a_project():
    provider = GeminiEnterpriseProvider({"location": "us-central1"})
    try:
        provider._client()
        assert False, "expected ProviderNotConfigured when no GCP project is configured"
    except ProviderNotConfigured as e:
        assert "project" in str(e).lower()


def test_gemini_enterprise_client_requires_project_even_with_empty_credentials_dict():
    provider = GeminiEnterpriseProvider({})
    try:
        provider._client()
        assert False, "expected ProviderNotConfigured when no GCP project is configured"
    except ProviderNotConfigured:
        pass


def test_gemini_enterprise_rejects_invalid_service_account_json():
    provider = GeminiEnterpriseProvider({"project_id": "demo-project", "service_account_json": "not json"})
    try:
        provider._client()
        assert False, "expected ProviderNotConfigured for invalid service account JSON"
    except ProviderNotConfigured as e:
        assert "json" in str(e).lower()
