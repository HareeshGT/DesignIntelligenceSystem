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


def test_multimodal_provider_requires_images():
    provider = LLMProvider(api_key="", model="vision-model")
    with pytest.raises(ProviderError, match="not configured"):
        provider.analyze_images_json("system", "prompt", [{"data": "aGVsbG8="}])


def test_multimodal_provider_rejects_unsupported_media_type():
    provider = LLMProvider(api_key="secret", model="vision-model")
    with pytest.raises(ProviderError, match="media type"):
        provider.analyze_images_json("system", "prompt", [{"data": "aGVsbG8=", "media_type": "image/gif"}])


def test_multimodal_provider_parses_json_from_mocked_openai_response(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"summary":"clear hierarchy","observations":[]}'}}]}

    captured = {}
    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return Response()

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    provider = LLMProvider(provider="openai-compatible", api_key="test", model="vision-model", base_url="https://example.test/v1")
    result = provider.analyze_images_json("system", "review", [{"data": "aGVsbG8=", "media_type": "image/jpeg"}])
    assert result["summary"] == "clear hierarchy"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["messages"][1]["content"][1]["type"] == "image_url"
