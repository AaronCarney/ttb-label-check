"""Upload size limits: what the service will accept before it reads anything.

Nothing bounded an upload before this. No byte cap on any upload path, no
`Content-Length` check, no body-size middleware — and `app/api/ui/submit.py`
reads every file in a submission into memory before it looks at any of them. A
single request could therefore decide how much memory the instance spends.

The numbers are derived in `app/api/limits.py` from three measured constraints,
and the first test here pins that derivation: a limit nobody can trace back to a
constraint gets moved the first time it is inconvenient.

Two layers, because they answer different questions:

  * the **request cap**, enforced by `BodySizeLimitMiddleware` before any body
    is read, is the memory guard. It is the only thing that can refuse a body
    that has not arrived yet, so it covers every route including ones not
    written yet.
  * the **per-file and per-batch caps**, enforced in the routes once multipart
    parsing has named the files, are what a person reads. They say which file
    was too big and what the limit is.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api import limits
from app.deps import reset_vision_extractor
from app.main import app
from tests._fakes.vision import FakeVisionExtractor

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def deterministic_seams(monkeypatch):
    monkeypatch.setattr(
        "app.deps.build_vision_extractor",
        lambda settings: FakeVisionExtractor(observations=[]),
    )
    reset_vision_extractor()
    yield
    reset_vision_extractor()


@pytest.fixture
def client():
    return TestClient(app)


def _png(size: int) -> bytes:
    return PNG + b"\x00" * max(0, size - len(PNG))


# --------------------------------------------------------------------------
# The numbers themselves
# --------------------------------------------------------------------------


def test_the_request_cap_sits_below_the_platform_cap() -> None:
    """Cloud Run refuses an HTTP/1 request body over 32 MiB itself, and
    `scripts/deploy.sh` sets no `--use-http2`. A cap at or above the platform's
    would mean Google's error page answers the user instead of ours, so the
    user is never told what the limit is or which file broke it."""
    assert limits.MAX_REQUEST_BYTES < limits.CLOUD_RUN_HTTP1_REQUEST_BYTES
    # Enough headroom for the HTTP request headers, which count towards the
    # platform's limit and sit outside the body `body_limit.py` measures. The
    # multipart boundaries and the form fields travel inside the body, so
    # `MAX_REQUEST_BYTES` already counts them and they need no reservation
    # here — the earlier 2 MiB floor reserved for them twice. A hundred parts
    # cost roughly 20 KB of boundary and header text; 256 KiB is an order of
    # magnitude above what the headers outside the body can be.
    assert limits.CLOUD_RUN_HTTP1_REQUEST_BYTES - limits.MAX_REQUEST_BYTES >= 256 * 1024


def test_one_file_can_never_fill_the_request_on_its_own() -> None:
    """A single image at the per-file cap must leave room for the rest of the
    request, or the two caps contradict each other and the user is told about
    whichever fires first."""
    assert limits.MAX_UPLOAD_BYTES < limits.MAX_REQUEST_BYTES


def test_a_full_batch_of_real_labels_fits_inside_the_request_cap() -> None:
    """NFR-2 asks for 300 submissions inside 10 minutes, which the file-count
    cap makes three batches of `MAX_BATCH_FILES`. That is only a real answer if
    a batch of that many actual labels fits in one request: the project's own 62
    corpus images have a median of ~184 KB and a maximum of ~560 KB."""
    median_label_bytes = 184 * 1024
    assert limits.MAX_BATCH_FILES * median_label_bytes < limits.MAX_REQUEST_BYTES


# --------------------------------------------------------------------------
# The request cap, before any body is read
# --------------------------------------------------------------------------


def test_an_oversized_request_is_refused_before_its_body_is_read(client, monkeypatch) -> None:
    """The point of the middleware. `Content-Length` says how big the body is
    before a byte of it arrives, so the refusal costs nothing."""
    monkeypatch.setattr(limits, "MAX_REQUEST_BYTES", 4096)
    response = client.post(
        "/labels",
        files={
            "application": (
                "a.json",
                json.dumps({"application_id": "A", "evaluation_id": "E"}),
                "application/json",
            ),
            "label": ("l.png", _png(8192), "image/png"),
        },
    )
    assert response.status_code == 413
    body = response.json()
    assert body["error_kind"] == "rejected_input"
    assert body["reason_code"] == "ENGINE.INPUT.REQUEST_TOO_LARGE"
    # The message has to name the limit, or the user cannot act on it.
    assert str(limits.MAX_REQUEST_BYTES) in json.dumps(body) or "4096" in body["message"]


def test_a_request_with_no_content_length_is_counted_as_it_streams(client, monkeypatch) -> None:
    """A chunked request declares no length, so the cap has to be enforced on
    the bytes as they arrive. Without this the middleware is bypassed by
    leaving one header off."""
    monkeypatch.setattr(limits, "MAX_REQUEST_BYTES", 4096)

    def _chunks():
        for _ in range(8):
            yield b"\x00" * 1024

    response = client.post(
        "/labels", content=_chunks(), headers={"content-type": "application/octet-stream"}
    )
    assert response.status_code == 413
    assert response.json()["reason_code"] == "ENGINE.INPUT.REQUEST_TOO_LARGE"


def test_a_request_inside_the_cap_is_untouched(client, deterministic_seams) -> None:
    response = client.post(
        "/labels",
        files={
            "application": (
                "a.json",
                json.dumps({"application_id": "A-001", "evaluation_id": "EV-001"}),
                "application/json",
            ),
            "label": ("l.png", _png(64), "image/png"),
        },
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# The per-file cap, named for the user
# --------------------------------------------------------------------------


def test_post_labels_refuses_an_oversized_image_by_name(
    client, monkeypatch, deterministic_seams
) -> None:
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 2048)
    response = client.post(
        "/labels",
        files={
            "application": (
                "a.json",
                json.dumps({"application_id": "A-001", "evaluation_id": "EV-001"}),
                "application/json",
            ),
            "label": ("big.png", _png(4096), "image/png"),
        },
    )
    assert response.status_code == 413
    body = response.json()
    assert body["reason_code"] == "ENGINE.INPUT.UPLOAD_TOO_LARGE"
    assert "big.png" in body["message"] or "big.png" in json.dumps(body["details"])


def test_the_upload_form_refuses_an_oversized_image(
    client, monkeypatch, deterministic_seams
) -> None:
    """The browser path answers in the page's own words, not a JSON envelope:
    a reviewer is looking at a form, not an API response."""
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 2048)
    response = client.post(
        "/",
        files={"labels": ("big.png", _png(4096), "image/png")},
        data={"beverage_type": "distilled_spirits"},
    )
    assert response.status_code == 413
    assert "big.png" in response.text


def test_the_upload_form_names_the_oversized_file_among_several(
    client, monkeypatch, deterministic_seams
) -> None:
    """The refusal names the file that was too big, not the submission. One
    label or several take the same route, so the naming has to survive a set."""
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 2048)
    response = client.post(
        "/",
        files=[
            ("labels", ("ok.png", _png(64), "image/png")),
            ("labels", ("big.png", _png(4096), "image/png")),
        ],
        data={"beverage_type": "distilled_spirits"},
    )
    assert response.status_code == 413
    assert "big.png" in response.text


# --------------------------------------------------------------------------
# The per-batch file count
# --------------------------------------------------------------------------


def test_a_batch_over_the_file_count_is_refused(client, monkeypatch, deterministic_seams) -> None:
    monkeypatch.setattr(limits, "MAX_BATCH_FILES", 3)
    response = client.post(
        "/",
        files=[("labels", (f"l{i}.png", _png(64), "image/png")) for i in range(4)],
        data={"beverage_type": "distilled_spirits"},
    )
    assert response.status_code == 413
    # The count and the limit both, so the user knows how far over they are.
    assert "3" in response.text and "4" in response.text


def test_a_batch_at_the_file_count_is_accepted(client, monkeypatch, deterministic_seams) -> None:
    """The cap is the largest batch accepted, not the first refused."""
    monkeypatch.setattr(limits, "MAX_BATCH_FILES", 3)
    response = client.post(
        "/",
        files=[("labels", (f"l{i}.png", _png(64), "image/png")) for i in range(3)],
        data={"beverage_type": "distilled_spirits"},
        follow_redirects=False,
    )
    assert response.status_code < 400
