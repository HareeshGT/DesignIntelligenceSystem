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
