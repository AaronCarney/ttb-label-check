"""Single-submission latency at the POST /labels chokepoint: P50 ≤ 2.7 s and
P99 ≤ 5.0 s, inside the five-second budget in docs/PRD.md NFR-1.

Measures the API, evaluator and serialization overhead against deterministic
seams — a fake reader. Reader load time is bypassed deliberately; it is
measured where it is spent, not here.
"""
import json
import statistics
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests._fakes.vision import FakeVisionExtractor


@pytest.fixture
def deterministic_seams(monkeypatch):
    monkeypatch.setattr(
        "app.deps.build_vision_extractor",
        lambda settings: FakeVisionExtractor(observations=[]),
    )


@pytest.mark.slow
def test_post_labels_perf_p50_p99(deterministic_seams):
    client = TestClient(app)
    payload = json.dumps({"application_id": "A-001", "evaluation_id": "EV-001"})
    image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    durations: list[float] = []
    for _ in range(30):
        t0 = time.monotonic()
        response = client.post("/labels", files={
            "application": ("a.json", payload, "application/json"),
            "label": ("l.png", image, "image/png"),
        })
        durations.append(time.monotonic() - t0)
        assert response.status_code == 200

    p50 = statistics.median(durations)
    p99 = sorted(durations)[max(0, int(len(durations) * 0.99) - 1)]
    print(f"\nperf: P50={p50:.3f}s P99={p99:.3f}s (n={len(durations)})")
    assert p50 <= 2.7, f"P50 {p50:.3f}s exceeds the 2.7s budget"
    assert p99 <= 5.0, f"P99 {p99:.3f}s exceeds the 5.0s budget"
