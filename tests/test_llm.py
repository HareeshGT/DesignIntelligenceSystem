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
    monkeypatch.setattr("app.services.llm.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))])
    provider = LLMProvider(provider="openai-compatible", api_key="test", model="vision-model", base_url="https://example.test/v1")
    result = provider.analyze_images_json("system", "review", [{"data": "aGVsbG8=", "media_type": "image/jpeg"}])
    assert result["summary"] == "clear hierarchy"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["messages"][1]["content"][1]["type"] == "image_url"


def test_multimodal_provider_rejects_null_text_content(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": None}}]}

    monkeypatch.setattr("app.services.llm.httpx.post", lambda *args, **kwargs: Response())
    provider = LLMProvider(provider="openai-compatible", api_key="test", model="vision-model")
    with pytest.raises(ProviderError, match="no text content"):
        provider.analyze_images_json("system", "review", [{"data": "aGVsbG8="}])


def test_complete_json_passes_requested_token_limit_to_anthropic(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"text": '{"ok":true}'}]}

    def fake_post(url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    provider = LLMProvider(provider="anthropic", api_key="test", model="claude-test")
    assert provider.complete_json("system", "prompt", max_tokens=8192) == {"ok": True}
    assert captured["max_tokens"] == 8192


def test_request_llm_uses_user_credentials_without_mutating_server_defaults(monkeypatch):
    from app.services.llm import request_llm

    monkeypatch.setenv("DIS_LLM_API_KEY", "server-secret")
    monkeypatch.setenv("DIS_LLM_MODEL", "server-model")
    monkeypatch.setattr("app.services.llm.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))])
    provider = request_llm(
        provider="anthropic",
        model="user-model",
        api_key="user-secret",
        base_url="https://user-provider.example/v1",
    )
    assert provider.provider == "anthropic"
    assert provider.model == "user-model"
    assert provider.api_key == "user-secret"
    assert provider.base_url == "https://user-provider.example/v1"
    assert LLMProvider().api_key == "server-secret"
    assert LLMProvider().model == "server-model"


def test_custom_model_endpoint_rejects_private_hosts():
    provider = LLMProvider(
        provider="openai-compatible", api_key="test", model="model",
        base_url="https://127.0.0.1:11434/v1",
    )
    with pytest.raises(ProviderError, match="public IP"):
        provider.complete_json("system", "prompt")


@pytest.mark.parametrize(
    ("provider", "expected_base"),
    [
        ("mistral", "https://api.mistral.ai/v1"),
        ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    ],
)
def test_provider_has_dedicated_default_endpoint(provider, expected_base):
    configured = LLMProvider(provider=provider, api_key="test", model="test-model", base_url="")
    assert configured.base_url == expected_base
    assert configured.enabled

def test_gemini_rejects_openai_endpoint_instead_of_sending_key_to_openai():
    provider = LLMProvider(
        provider="gemini",
        api_key="test-gemini-key",
        model="gemini-2.5-flash",
        base_url="https://api.openai.com/v1",
    )

    with pytest.raises(ProviderError, match="selected gemini provider is configured with the openai API endpoint"):
        provider.complete_json("system", "prompt")


def test_provider_http_errors_expose_safe_diagnostic_and_redact_api_key(monkeypatch):
    import httpx

    secret = "test-provider-secret-key"
    response = httpx.Response(
        400,
        json={"error": {"message": f"Invalid model request for key {secret}"}},
        request=httpx.Request("POST", "https://provider.example/v1/chat/completions"),
    )
    monkeypatch.setattr("app.services.llm.httpx.post", lambda *args, **kwargs: response)
    monkeypatch.setattr("app.services.llm.LLMProvider._validate_custom_base_url", lambda self: None)
    provider = LLMProvider(
        provider="gemini", api_key=secret, model="test-model",
        base_url="https://provider.example/v1",
    )

    with pytest.raises(ProviderError) as error:
        provider.complete_json("system", "prompt")

    assert "HTTP 400" in str(error.value)
    assert "Invalid model request" in str(error.value)
    assert secret not in str(error.value)


def test_provider_timeout_has_actionable_error(monkeypatch):
    import httpx

    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("request timed out")

    monkeypatch.setattr("app.services.llm.httpx.post", timeout)
    monkeypatch.setattr("app.services.llm.LLMProvider._validate_custom_base_url", lambda self: None)
    provider = LLMProvider(provider="gemini", api_key="test", model="test-model")

    with pytest.raises(ProviderError, match="timed out"):
        provider.complete_json("system", "prompt")

