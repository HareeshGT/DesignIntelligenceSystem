import pytest

from app.services.llm import LLMProvider, ProviderError


def test_provider_is_disabled_without_credentials():
    provider = LLMProvider(api_key="", model="gpt-test")
    assert provider.enabled is False
    with pytest.raises(ProviderError, match="not configured"):
        provider.complete_json("system", "prompt")


def test_provider_parses_json_response():
    assert LLMProvider._parse_json('{"summary":"ready","findings":[]}') == {
        "summary": "ready", "findings": []
    }


def test_provider_parses_fenced_json_response():
    assert LLMProvider._parse_json(' ```json\n{"ok":true}\n``` ') == {"ok": True}


def test_provider_rejects_non_object_json():
    with pytest.raises(ProviderError, match="JSON object"):
        LLMProvider._parse_json('["not", "an object"]')


def test_provider_rejects_invalid_json():
    with pytest.raises(ProviderError, match="valid JSON"):
        LLMProvider._parse_json("not json")
