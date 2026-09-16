"""Settings: env-var loading, defaults, missing-required errors."""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest


@contextmanager
def _env(**overrides: str | None):
    original = {k: os.environ.get(k) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_settings_defaults_when_only_required_provided() -> None:
    from app.config import Settings

    with _env(
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY=None,
        VISION_MODE=None,
        ORCHESTRATOR_BACKEND=None,
        LOOKAHEAD_K=None,
        DEV_MODE=None,
        OTEL_EXPORTER_OTLP_ENDPOINT=None,
        LLM_MODEL_SNAPSHOT=None,
        PROMPT_VERSION=None,
    ):
        s = Settings()
        assert s.vision_mode == "cloud"
        assert s.orchestrator_backend == "openai"
        assert s.lookahead_k == 3
        assert s.dev_mode is False
        assert s.llm_model_snapshot == "gpt-4o-2024-08-06"
        assert s.prompt_version == "v1"


def test_settings_lookahead_k_int_coercion() -> None:
    from app.config import Settings

    with _env(OPENAI_API_KEY="sk-test", LOOKAHEAD_K="5"):
        s = Settings()
        assert s.lookahead_k == 5


def test_settings_dev_mode_truthy_strings() -> None:
    from app.config import Settings

    with _env(OPENAI_API_KEY="sk-test", DEV_MODE="1"):
        assert Settings().dev_mode is True
    with _env(OPENAI_API_KEY="sk-test", DEV_MODE="true"):
        assert Settings().dev_mode is True
    with _env(OPENAI_API_KEY="sk-test", DEV_MODE=""):
        assert Settings().dev_mode is False


def test_settings_rejects_invalid_vision_mode() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    with _env(OPENAI_API_KEY="sk-test", VISION_MODE="banana"):
        with pytest.raises(ValidationError):
            Settings()
