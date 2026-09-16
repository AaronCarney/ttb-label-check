import pytest

from app.config import Settings
from app.deps import build_orchestrator
from app.orchestrator.openai_strict import OpenAIStrictOrchestrator
from app.orchestrator.anthropic_strict import AnthropicStrictOrchestrator


def test_build_orchestrator_openai(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_BACKEND", "openai")
    settings = Settings()
    orch = build_orchestrator(settings)
    assert isinstance(orch, OpenAIStrictOrchestrator)


def test_build_orchestrator_anthropic(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_BACKEND", "anthropic")
    settings = Settings()
    orch = build_orchestrator(settings)
    assert isinstance(orch, AnthropicStrictOrchestrator)


def test_build_orchestrator_unknown_raises(monkeypatch):
    """Settings restricts orchestrator_backend Literal so 'vllm' fails at Settings()
    construction with ValidationError. The build_orchestrator function additionally
    raises ValueError if a future placeholder leaks through."""
    from pydantic import ValidationError
    monkeypatch.setenv("ORCHESTRATOR_BACKEND", "vllm")
    with pytest.raises(ValidationError):
        Settings()


def test_placeholder_classes_removed():
    """No placeholder orchestrator survives in app.deps."""
    import app.deps as deps
    assert not hasattr(deps, "_PlaceholderOpenAIOrchestrator")
    assert not hasattr(deps, "_PlaceholderAnthropicOrchestrator")
