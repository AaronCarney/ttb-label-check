"""App factory wires healthz route + startup hook + logging configuration."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_app_module_exposes_app_object() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import app  # noqa: F401

    assert app is not None


def test_app_registers_healthz_route() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/healthz" in paths


def test_app_factory_function_is_idempotent() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import create_app

    a = create_app()
    b = create_app()
    assert a is not b
    assert {r.path for r in a.routes} == {r.path for r in b.routes}


def test_app_responds_200_to_healthz_via_test_client() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    from app.main import app

    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
