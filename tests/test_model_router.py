"""model_router 邏輯測試。"""
from backend.model_router import resolve_gemini_model, resolve_provider


def test_default_provider_is_gemini(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_PROVIDER_QUALITY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert resolve_provider(tier="quality") == "gemini"


def test_provider_claude_when_key_exists(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    assert resolve_provider(tier="quality") == "claude"


def test_gemini_model_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL_QUALITY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL_CHEAP", raising=False)
    assert "gemini" in resolve_gemini_model(tier="quality")
    assert "gemini" in resolve_gemini_model(tier="cheap")
