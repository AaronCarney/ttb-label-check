""".env.example documents every environment variable the app reads."""
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


def test_env_example_documents_all_required_keys() -> None:
    path = Path(__file__).parents[1] / ".env.example"
    assert path.exists(), ".env.example must exist at repo root"
    keys = _parse_env_example(path)
    missing = REQUIRED_KEYS - keys
    assert not missing, f"missing env-var entries in .env.example: {sorted(missing)}"
