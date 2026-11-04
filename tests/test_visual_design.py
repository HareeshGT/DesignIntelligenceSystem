from app.services.visual_design import VisualDesignAnalyzer

def test_visual_analyzer_supports_dedicated_vision_provider(monkeypatch):
    monkeypatch.setenv("DIS_VISION_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DIS_VISION_LLM_API_KEY", "vision-key")
    monkeypatch.setenv("DIS_VISION_LLM_MODEL", "vision-model")
    monkeypatch.setenv("DIS_VISION_LLM_BASE_URL", "https://vision.example/v1")
    analyzer = VisualDesignAnalyzer()
    assert analyzer.provider.provider == "openai-compatible"
    assert analyzer.provider.api_key == "vision-key"
    assert analyzer.provider.model == "vision-model"
    assert analyzer.provider.base_url == "https://vision.example/v1"


def test_visual_analyzer_truncates_model_findings_to_schema_limits():
    class FakeProvider:
        enabled = True

        def analyze_images_json(self, **kwargs):
            return {
                "summary": "ok",
                "observations": [{
                    "category": "c" * 120,
                    "severity": "medium",
                    "title": "t" * 240,
                    "description": "d" * 800,
                    "evidence": "e" * 800,
                    "recommendation": "r" * 800,
                }],
                "design_system": {},
            }

    result = VisualDesignAnalyzer(provider=FakeProvider()).analyze([
        {"name": "desktop", "data": "ZmFrZQ=="}
    ])
    finding = result["findings"][0]
    assert len(finding.category) == 80
    assert len(finding.title) == 180
    assert len(finding.description) == 600
    assert len(finding.evidence) == 600
    assert len(finding.recommendation) == 600


def test_partial_dedicated_vision_config_never_falls_back_to_text_credentials(monkeypatch):
    monkeypatch.setenv("DIS_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DIS_LLM_API_KEY", "text-secret")
    monkeypatch.setenv("DIS_LLM_MODEL", "text-model")
    monkeypatch.setenv("DIS_LLM_BASE_URL", "https://text-provider.example/v1")
    monkeypatch.delenv("DIS_VISION_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DIS_VISION_LLM_API_KEY", "")
    monkeypatch.setenv("DIS_VISION_LLM_MODEL", "vision-model")
    monkeypatch.delenv("DIS_VISION_LLM_BASE_URL", raising=False)

    provider = VisualDesignAnalyzer().provider
    assert provider.api_key == ""
    assert provider.model == "vision-model"
    assert provider.base_url == ""
    assert provider.enabled is False


def test_no_dedicated_vision_config_reuses_complete_text_provider(monkeypatch):
    monkeypatch.setenv("DIS_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DIS_LLM_API_KEY", "text-secret")
    monkeypatch.setenv("DIS_LLM_MODEL", "text-model")
    monkeypatch.setenv("DIS_LLM_BASE_URL", "https://text-provider.example/v1")
    for name in ("DIS_VISION_LLM_PROVIDER", "DIS_VISION_LLM_API_KEY", "DIS_VISION_LLM_MODEL", "DIS_VISION_LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    provider = VisualDesignAnalyzer().provider
    assert provider.api_key == "text-secret"
    assert provider.model == "text-model"
    assert provider.base_url == "https://text-provider.example/v1"
