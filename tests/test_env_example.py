""".env.example and app/config.py describe the same set of variables.

Two directions, and both have failed elsewhere in this tree: a variable the app
reads that nobody documents, and a variable documented that nothing reads. The
second is the quieter failure — it reads as a working switch and is not one.
"""
from __future__ import annotations

from pathlib import Path

REQUIRED_KEYS = {
    "VISION_MODE",
    "OPENAI_API_KEY",
    "LLM_MODEL_SNAPSHOT",
    "PROMPT_VERSION",
    "LOOKAHEAD_K",
    "DEV_MODE",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
}

ENV_EXAMPLE = Path(__file__).parents[1] / ".env.example"


def _parse_env_example(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _settings_aliases() -> set[str]:
    from app.config import Settings

    return {
        (field.alias or name).upper()
        for name, field in Settings.model_fields.items()
    }


def test_env_example_documents_all_required_keys() -> None:
    assert ENV_EXAMPLE.exists(), ".env.example must exist at repo root"
    missing = REQUIRED_KEYS - _parse_env_example(ENV_EXAMPLE)
    assert not missing, f"missing env-var entries in .env.example: {sorted(missing)}"


def test_env_example_documents_nothing_the_app_does_not_read() -> None:
    """A documented variable the app never reads is a switch that does nothing."""
    documented = {k.upper() for k in _parse_env_example(ENV_EXAMPLE)}
    unread = sorted(documented - _settings_aliases())
    assert not unread, f".env.example documents variables nothing reads: {unread}"
