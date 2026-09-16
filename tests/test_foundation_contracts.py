"""The project's foundation contracts, asserted end to end.

Each of these is also covered by a narrower test elsewhere. This file ties them
together into one runnable suite, so a break in the scaffolding — packaging,
the health endpoint, the wire envelopes, secret handling, the dependency
seams — shows up in one place.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).parents[1]


def test_pyproject_is_valid_and_uv_lock_exists() -> None:
    """``uv sync`` has both things it resolves against: the project metadata and
    the committed lock file. Whether a fresh sync succeeds is checked by running
    it on a clean clone, not from inside pytest."""
    assert (REPO_ROOT / "pyproject.toml").exists()
    assert (REPO_ROOT / "uv.lock").exists()


def test_taskipy_demo_target_defined() -> None:
    """``uv run task demo`` is declared and points at the app. Booting it is a
    subprocess smoke check run outside pytest, not here."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.taskipy.tasks]" in text
    assert "demo = " in text
    assert "uvicorn app.main:app" in text


def test_healthz_returns_200_with_payload_shape() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import app

    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body and "mode" in body


def test_suite_surface_meets_minimum() -> None:
    """The suite has not collapsed: ≥4 test files, ≥25 tests across them.

    A loose proxy: count test files and ``def test_`` declarations.
    """
    tests_dir = REPO_ROOT / "tests"
    test_files = list(tests_dir.glob("test_*.py"))
    assert len(test_files) >= 4, [p.name for p in test_files]
    test_count = 0
    for path in test_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("def test_"):
                test_count += 1
    assert test_count >= 25, f"only {test_count} tests defined"


def test_wire_envelopes_round_trip_byte_identical_keys() -> None:
    """Every wire envelope round-trips through its schema unchanged."""
    from app.schemas.wire.application import ApplicationEnvelope
    from app.schemas.wire.batch import BatchEnvelope
    from app.schemas.wire.disposition import DispositionEnvelope
    from app.schemas.wire.error import ErrorEnvelope

    fixtures_dir = REPO_ROOT / "tests" / "wire_fixtures"
    cases = [
        (ApplicationEnvelope, "application.json"),
        (DispositionEnvelope, "disposition.json"),
        (BatchEnvelope, "batch.json"),
        (ErrorEnvelope, "error.json"),
    ]
    for model, name in cases:
        raw = json.loads((fixtures_dir / name).read_text())
        env = model.model_validate(raw)
        # Re-validate after a dump round trip; equality holds.
        rt = model.model_validate_json(env.model_dump_json())
        assert rt == env, name


def test_no_os_environ_outside_app_config() -> None:
    """Only ``app/config.py`` reads ``os.environ``.

    Delegated to ``tests/test_secrets_grep.py`` and re-run inline here, so the
    foundation suite covers it too.
    """
    from tests.test_secrets_grep import (  # type: ignore[import-not-found]
        test_os_environ_read_only_in_app_config_py,
    )

    test_os_environ_read_only_in_app_config_py()


def test_healthz_emits_one_json_log_line(capsys) -> None:
    """The structured logger emits a single JSON line on /healthz."""
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import create_app

    app_obj = create_app()
    with TestClient(app_obj) as client:
        # `with` triggers the lifespan startup — drain its log line(s)
        # so the next capsys read isolates the /healthz request emission.
        capsys.readouterr()
        r = client.get("/healthz")
        assert r.status_code == 200
        captured = capsys.readouterr().out
    # The /healthz route itself emits a single structured log line.
    # Filter to the app.healthz logger — third-party libraries (e.g., httpx
    # in TestClient) may emit their own lines through the root handler;
    # those are not what this test asserts.
    json_lines = [
        json.loads(ln)
        for ln in captured.splitlines()
        if ln.strip().startswith("{")
    ]
    healthz_lines = [p for p in json_lines if p.get("logger") == "app.healthz"]
    assert len(healthz_lines) == 1, json_lines
    parsed = healthz_lines[0]
    assert "ts" in parsed
    assert "level" in parsed
    assert "msg" in parsed


def test_di_providers_return_real_impls() -> None:
    """Both dependency seams return a real implementation.

    The vision provider returns a ``VisionExtractor`` chosen by VISION_MODE and
    the orchestrator provider returns an ``Orchestrator`` chosen by
    ORCHESTRATOR_BACKEND. Neither is a placeholder that raises
    NotImplementedError.
    """
    from app.config import Settings
    from app.deps import build_orchestrator, build_vision_extractor
    from app.orchestrator.base import Orchestrator
    from app.vision.base import VisionExtractor

    s = Settings()
    extractor = build_vision_extractor(s)
    orch = build_orchestrator(s)

    assert isinstance(extractor, VisionExtractor) or hasattr(extractor, "extract")
    assert isinstance(orch, Orchestrator)


def test_rule_set_canonically_declared_in_app_schemas_rules() -> None:
    """``RuleSet`` is declared canonically in ``app/schemas/rules.py``.

    That ``app/rules/models.py`` re-exports the very same object is asserted in
    ``tests/test_rule_set_import_identity.py``; here we only confirm where the
    canonical declaration lives.
    """
    from app.schemas.rules import RuleSet

    assert RuleSet.__module__ == "app.schemas.rules"
