"""POST /labels — multipart parsing, validation, delegation (deterministic)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.deps import reset_vision_extractor
from app.main import app
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor


@pytest.fixture
def deterministic_seams(monkeypatch):
    """Wire fakes into the build_evaluator factory so the endpoint test
    exercises only the Application Service / serialization path."""
    monkeypatch.setattr(
        "app.deps.build_vision_extractor",
        lambda settings: FakeVisionExtractor(observations=[]),
    )
    # The reader is shared per process (``app/deps.py``), so drop whatever is
    # cached: before, so this test gets the fake, and after, so the next test
    # does not inherit it.
    reset_vision_extractor()
    yield
    reset_vision_extractor()


def test_post_labels_happy_path(deterministic_seams):
    client = TestClient(app)
    payload = {"application_id": "A-001", "evaluation_id": "EV-001"}
    files = {
        "application": ("a.json", json.dumps(payload), "application/json"),
        "label": ("l.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, "image/png"),
    }
    response = client.post("/labels", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_id"] == "EV-001"
    assert body["disposition"] in {"pass", "fail", "needs_review"}
    assert body["disposition"]


def test_post_labels_rejects_tiff():
    client = TestClient(app)
    payload = {"application_id": "A-001", "evaluation_id": "EV-001"}
    files = {
        "application": ("a.json", json.dumps(payload), "application/json"),
        "label": ("l.tiff", b"II*\x00" + b"\x00" * 12, "image/tiff"),
    }
    response = client.post("/labels", files=files)
    assert response.status_code == 400


def test_post_labels_rejects_malformed_json():
    client = TestClient(app)
    files = {
        "application": ("a.json", "not-json", "application/json"),
        "label": ("l.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, "image/png"),
    }
    response = client.post("/labels", files=files)
    assert response.status_code == 400
