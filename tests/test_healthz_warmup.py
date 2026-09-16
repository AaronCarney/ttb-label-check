"""/healthz upgraded — runs full sentinel pipeline against fixture-01."""
import time

import pytest
from fastapi.testclient import TestClient

from app.api.healthz import _warmed
from app.main import app


@pytest.fixture(autouse=True)
def _reset_warmed():
    _warmed["done"] = False
    yield
    _warmed["done"] = False


def test_healthz_first_invocation_runs_warmup():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "warmup_ran" in body or "sentinel_disposition" in body


def test_healthz_warm_call_under_2s():
    client = TestClient(app)
    client.get("/healthz")  # warm
    t0 = time.monotonic()
    response = client.get("/healthz")
    elapsed = time.monotonic() - t0
    assert response.status_code == 200
    assert elapsed < 2.0, f"warm /healthz took {elapsed:.2f}s, expected < 2s"
