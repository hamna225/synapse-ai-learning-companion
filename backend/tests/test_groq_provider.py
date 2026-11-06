import pytest

from agents import groq_provider


def test_groq_provider_uses_configured_server_key_and_json_mode(monkeypatch):
    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.options = kwargs

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GROQ_RESUME_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    model = groq_provider.get_groq_text_model(json_mode=True)
    assert model.options["api_key"] == "test-groq-key"
    assert model.options["base_url"] == "https://api.groq.com/openai/v1"
    assert model.options["model_kwargs"]["response_format"] == {"type": "json_object"}


def test_groq_provider_reports_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        groq_provider.get_groq_text_model()
