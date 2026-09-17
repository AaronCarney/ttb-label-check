"""``GET /healthz`` answers 503 ``not_ready`` when the process cannot get ready.

Readiness is the whole point of the endpoint: an orchestrator holds traffic back
on a 503 and releases it on a 200, so the failure answer needs a guard of its
own, and so does the retry that follows it.

The evaluator build is stubbed throughout. The real one loads the OCR models off
disk, which costs about a second and is not what these assertions are about.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import healthz


@pytest.fixture(autouse=True)
def _cold_process():
    """Start each test with the process marked not-yet-ready, and leave it so."""
    healthz._warmed["done"] = False
    yield
    healthz._warmed["done"] = False


def _client() -> TestClient:
    """A bare app carrying the health route and nothing else."""
    app = FastAPI()
    app.include_router(healthz.router)
    return TestClient(app)


class _StubEvaluator:
    """Stands in for the real evaluator; records how the reader was warmed.

    It counts the two separately because the endpoint has to call the outer
    one. ``ensure_loaded`` builds the models and stops there, leaving the first
    inference for whoever submits first; ``warm`` loads *and* runs one read, so
    nothing is left to pay. Mirroring the real reader, ``warm`` awaits
    ``ensure_loaded`` itself, so a double that only counted loads could not
    tell the two apart.
    """

    def __init__(self) -> None:
        self._vision = self
        self.loads = 0
        self.warms = 0

    async def ensure_loaded(self) -> None:
        self.loads += 1

    async def warm(self) -> None:
        self.warms += 1
        await self.ensure_loaded()


def test_healthz_answers_503_not_ready_when_the_reader_will_not_load(monkeypatch) -> None:
    import app.deps

    def _fails(settings):
        raise RuntimeError("no OCR models on disk")

    monkeypatch.setattr(app.deps, "build_evaluator", _fails)

    response = _client().get("/healthz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["warmup_error"] == "no OCR models on disk"
    assert body["warmup_ran"] is False


def test_a_failed_probe_leaves_the_process_free_to_try_again(monkeypatch) -> None:
    import app.deps

    evaluator = _StubEvaluator()
    calls = {"n": 0}

    def _fails_once_then_works(settings):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("models still being written")
        return evaluator

    monkeypatch.setattr(app.deps, "build_evaluator", _fails_once_then_works)

    client = _client()
    assert client.get("/healthz").status_code == 503
    assert healthz._warmed["done"] is False, "a failed probe must not mark the process ready"

    retry = client.get("/healthz")

    assert retry.status_code == 200
    assert retry.json()["status"] == "ok"
    assert retry.json()["warmup_ran"] is True
    assert calls["n"] == 2, "the retry has to build the evaluator again, not reuse the failure"
    assert evaluator.loads == 1
    assert evaluator.warms == 1, (
        "the probe has to warm the reader, not merely load it: loading builds "
        "the models and leaves the first inference for the first label"
    )


def test_once_ready_later_calls_answer_from_process_state(monkeypatch) -> None:
    import app.deps

    evaluator = _StubEvaluator()
    calls = {"n": 0}

    def _works(settings):
        calls["n"] += 1
        return evaluator

    monkeypatch.setattr(app.deps, "build_evaluator", _works)

    client = _client()
    first = client.get("/healthz")
    second = client.get("/healthz")

    assert first.status_code == 200
    assert first.json()["warmup_ran"] is True
    assert second.status_code == 200
    assert second.json()["warmup_ran"] is False, "a warm call reports no fresh readiness work"
    assert calls["n"] == 1, "readiness is proved once per process, not per request"
