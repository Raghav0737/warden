"""Tests for warden.config settings and Groq LLM client."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from pydantic import SecretStr

from warden.config import Settings, get_groq_llm
from warden.demo_graph import draft_node


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in [
        "CONNECTION_STRING",
        "DATABASE_URL",
        "POSTGRES_URI",
        "POSTGRES_URL",
        "WARDEN_PG_URI",
        "GROQ_API_KEY",
        "GROQ_MODEL",
    ]:
        monkeypatch.delenv(k, raising=False)

    s = Settings(
        groq_api_key=None,
        postgres_uri=None,
    )
    assert s.groq_api_key is None
    assert s.postgres_uri is None
    assert s.groq_model == "openai/gpt-oss-20b"


@pytest.mark.parametrize(
    "env_key",
    ["CONNECTION_STRING", "DATABASE_URL", "POSTGRES_URI", "POSTGRES_URL", "WARDEN_PG_URI"],
)
def test_settings_postgres_aliases(
    monkeypatch: pytest.MonkeyPatch, env_key: str
) -> None:
    uri = "postgresql://user:pass@localhost:5432/testdb"
    for k in [
        "CONNECTION_STRING",
        "DATABASE_URL",
        "POSTGRES_URI",
        "POSTGRES_URL",
        "WARDEN_PG_URI",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(env_key, uri)

    s = Settings()
    assert s.postgres_uri == uri


def test_settings_groq_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
    monkeypatch.setenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    s = Settings()
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk_test123"
    assert s.groq_model == "qwen/qwen3.8-27b"


def test_get_groq_llm_none_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from warden import config

    monkeypatch.setattr(config.settings, "groq_api_key", None)
    assert get_groq_llm() is None


def test_get_groq_llm_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from warden import config

    monkeypatch.setattr(config.settings, "groq_api_key", SecretStr("gsk_test123"))
    monkeypatch.setattr(config.settings, "groq_model", "openai/gpt-oss-20b")

    llm = get_groq_llm()
    assert llm is not None
    assert llm.model_name == "openai/gpt-oss-20b"
    assert str(llm.openai_api_base).rstrip("/") == "https://api.groq.com/openai/v1"


def test_draft_node_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from warden import config

    monkeypatch.setattr(config.settings, "groq_api_key", None)
    out = draft_node({"messages": [], "approved": False})
    assert "Drafted email: 'Weekly report ready'" in out["messages"][0]


def test_draft_node_with_groq_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_llm = MagicMock()
    mock_llm.model_name = "openai/gpt-oss-20b"
    mock_response = MagicMock()
    mock_response.content = "System health is 100% operational."
    mock_llm.invoke.return_value = mock_response

    monkeypatch.setattr("warden.demo_graph.get_groq_llm", lambda: mock_llm)

    out = draft_node({"messages": ["Weekly report ready"], "approved": False})
    assert "Drafted email via Groq:" in out["messages"][0]
    assert "System health is 100% operational." in out["messages"][0]
