"""Deterministic tests for the multi-provider ModelRegistry, plus BedrockProvider's pure/sync
config-validation paths. No DB/network — mirrors the pattern in test_devstudio_execution_service.py.
"""
from app.devstudio.providers.base import ProviderNotConfigured
from app.devstudio.providers.bedrock_provider import BedrockProvider
from app.devstudio.providers.registry import MODEL_PRESETS, known_provider_names, preset_for_role


def test_known_provider_names_includes_bedrock_alongside_the_others():
    names = known_provider_names()
    assert set(names) == {"anthropic", "openai", "gemini", "bedrock", "emergent"}


def test_bedrock_not_used_by_any_preset_by_default():
    # Bedrock/Emergent are opt-in per-role overrides (Settings > Agents), not preset defaults —
    # nothing in MODEL_PRESETS should silently route through them.
    for preset in MODEL_PRESETS.values():
        for cfg in preset.values():
            assert cfg["primary_provider"] not in ("bedrock", "emergent")
            assert cfg["fallback_provider"] not in ("bedrock", "emergent")


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
