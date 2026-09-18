"""What commit is running must be answerable from the service itself.

Once, the question "are these five fixes live?" could not be answered
from Cloud Run at all: every revision's metadata carried a timestamp and an
image digest, and neither names a commit. The revision timeline said the deploy
was newer than the commits, which was true and still did not mean the commits
were in it. Settling it took a behavioural probe against the live service.

A deploy that does not say what it deployed is the fault these hold shut, from
both ends: the script stamps the commit it archived, and the health endpoint
reports the stamp it was given.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

SCRIPT = Path("scripts/deploy.sh")


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text()


def test_deploy_stamps_the_commit_it_archived(script: str) -> None:
    """The deploy uploads `git archive HEAD`, so HEAD is what runs. The same
    revision of the same commit must be readable back off the service."""
    assert re.search(r"GIT_COMMIT=", script), (
        "scripts/deploy.sh does not pass GIT_COMMIT, so the running service "
        "cannot say which commit it is"
    )
    assert re.search(r"COMMIT=\"?\$\(git rev-parse HEAD\)", script), (
        "the stamp must be HEAD, the commit `git archive` uploads; anything "
        "else can name a commit the image was not built from"
    )


def test_deploy_labels_the_revision_with_the_commit(script: str) -> None:
    """A label is readable with `gcloud run revisions list` without starting the
    container, which is what a person asking "what is live" reaches for first."""
    assert "--labels" in script, (
        "scripts/deploy.sh passes no --labels, so revision metadata still names no commit"
    )


def _health_app() -> FastAPI:
    from app.api.healthz import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def _cheap_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """`cloud` mode so the warm-up loads no model: the hosted reader loads
    nothing, and this test is about the payload, not the reader."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VISION_MODE", "cloud")


def test_health_reports_the_commit_it_was_stamped_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_COMMIT", "0123456789abcdef0123456789abcdef01234567")
    body = TestClient(_health_app()).get("/api/health").json()
    assert body["commit"] == "0123456789abcdef0123456789abcdef01234567"


def test_health_says_unknown_rather_than_omitting_the_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent key reads as an old build of the app; "unknown" reads as a
    deploy that did not stamp itself. They are different faults."""
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    body = TestClient(_health_app()).get("/api/health").json()
    assert body["commit"] == "unknown"


def test_env_example_documents_the_stamp() -> None:
    """The app reads it, so it is documented — and documented as deploy-set, not
    as a switch anyone should fill in by hand."""
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "GIT_COMMIT" in text
