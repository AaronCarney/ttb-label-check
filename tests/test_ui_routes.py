"""The page-shell GET routes and the StaticFiles mount.

These routes serve Jinja templates only; the engine is reached through the API
routes. The test guards: (a) /healthz is unaffected by registering the UI,
(b) GET / returns the single-mode shell with data-mode="single",
(c) GET /batch/{batch_id} returns the batch shell with data-mode="batch" and
    data-batch-id="{batch_id}",
(d) /static/island/.gitkeep is served (proves the StaticFiles mount works).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_settings
from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def dev_client() -> TestClient:
    """Client with DEV_MODE=1 forced through a dependency override."""
    app = create_app()
    app.dependency_overrides[_get_settings] = lambda: Settings(DEV_MODE="1")
    return TestClient(app)


def test_healthz_still_passes(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_single_page_shell(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="root"' in response.text
    assert 'data-mode="single"' in response.text
    assert "/static/island/single.js" in response.text
    # The noscript fallback, for a browser with JavaScript turned off.
    assert "<noscript>" in response.text
    assert "POST /labels" in response.text


def test_batch_page_shell(client: TestClient) -> None:
    response = client.get("/batch/abc-123")
    assert response.status_code == 200
    assert 'data-mode="batch"' in response.text
    assert 'data-batch-id="abc-123"' in response.text
    assert "/static/island/batch.js" in response.text


def test_static_island_mount(client: TestClient) -> None:
    """The StaticFiles mount serves files under app/ui/static/. The sentinel is
    /static/island/style.css, a file the build itself emits — Vite's emptyOutDir
    wipes any placeholder on every build, so a placeholder cannot be used."""
    response = client.get("/static/island/style.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_dev_mode_off_by_default(client: TestClient) -> None:
    """RawJSONDrawer guard (single.tsx) reads body[data-dev-mode] — default is '0'."""
    response = client.get("/")
    assert 'data-dev-mode="0"' in response.text


def test_dev_mode_on_when_settings_enabled(dev_client: TestClient) -> None:
    """When DEV_MODE=1, the body attribute lets the React island render the
    RawJSONDrawer. The single and batch shells both honour it."""
    single = dev_client.get("/")
    assert 'data-dev-mode="1"' in single.text
    batch = dev_client.get("/batch/abc-123")
    assert 'data-dev-mode="1"' in batch.text


def test_uswds_skip_link_present(client: TestClient) -> None:
    """NFR-A11Y-002 keyboard-operable end-to-end: the 'Skip to main content'
    link must be the first focusable element on every page."""
    response = client.get("/")
    assert 'class="skip-link"' in response.text
    assert "Skip to main content" in response.text


def test_root_renders_empty_inbox(client: TestClient) -> None:
    """A cold visit to `/` shows the empty-inbox landing — no pre-loaded
    fixture envelope, no review surface populated. The metaphor is a
    reviewer starting a shift with nothing in their queue."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Your inbox is empty" in response.text
    assert "Drop new labels here" in response.text
    # No fixture envelopes embedded — review surface stays a placeholder
    # until an upload returns a real envelope.
    assert "FIX-01-SPIRITS-CLEAN" not in response.text
    assert 'id="envelope"' not in response.text


def test_root_links_to_starter_pack(client: TestClient) -> None:
    """The empty-inbox landing must surface the starter-pack download so a
    reviewer without their own labels can still try the pipeline."""
    response = client.get("/")
    assert "/batches/sample.zip" in response.text
    assert "starter pack" in response.text.lower()


def test_root_no_longer_serves_fixture_query(client: TestClient) -> None:
    """`?fixture=NN` is no longer wired — bare `/` and `/?fixture=02` both
    render the same empty-inbox shell. Param is silently ignored."""
    bare = client.get("/")
    with_param = client.get("/?fixture=02")
    assert bare.status_code == 200
    assert with_param.status_code == 200
    assert "Your inbox is empty" in with_param.text
    assert "FIX-02-STONES-THROW" not in with_param.text


# ---------------------------------------------------------------------------
# Single-label upload widget — POST /
# ---------------------------------------------------------------------------

def test_upload_form_present_on_root(client: TestClient) -> None:
    """The reviewer needs an in-page upload affordance — a multipart POST form
    targeting `/` with a file input named `label`."""
    response = client.get("/")
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="label"' in response.text
    assert 'method="post"' in response.text or 'method="POST"' in response.text


def test_upload_with_real_image_returns_envelope() -> None:
    """A multipart POST to / with a PNG runs the evaluator and re-renders the
    shell with the live envelope. Uses dependency override to swap the
    real evaluator for a stub so the test never calls OpenAI."""
    from app.api.ui import _get_upload_evaluator
    from tests._fakes.evaluator import FakeEvaluator
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    env = _stub_disposition_envelope(99, disposition="pass")
    fake = FakeEvaluator([(0.0, env)])
    app.dependency_overrides[_get_upload_evaluator] = lambda: fake
    client = TestClient(app)

    # Tiny valid PNG (1x1 black pixel).
    png_1x1 = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
        "0001a5f645400000000049454e44ae426082"
    )
    response = client.post(
        "/",
        files={"label": ("upload.png", png_1x1, "image/png")},
    )
    assert response.status_code == 200, response.text
    assert "EV-0099" in response.text  # evaluation_id from stub envelope
    assert "lbl-0099" in response.text  # label_ref


def test_upload_with_invalid_mime_renders_error() -> None:
    """An obviously-not-an-image upload should re-render the page with an
    inline error banner rather than 500ing or showing a stack trace."""
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/",
        files={"label": ("not_an_image.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    assert "unsupported" in response.text.lower() or "png" in response.text.lower()


def test_upload_without_file_returns_422() -> None:
    """FastAPI's File(...) requirement should produce a 422 when missing."""
    app = create_app()
    client = TestClient(app)
    response = client.post("/", files={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Bulk upload page — GET /batches + POST /batches/upload
# ---------------------------------------------------------------------------

# A tiny valid PNG used across the bulk-upload tests.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


def test_batches_upload_page_present(client: TestClient) -> None:
    """A reviewer needs a top-level entry to bulk submission. `GET /batches`
    should serve a multipart form whose file input accepts multiple files."""
    response = client.get("/batches")
    assert response.status_code == 200
    assert 'enctype="multipart/form-data"' in response.text
    assert "multiple" in response.text
    assert 'name="labels"' in response.text


def test_root_links_to_bulk_upload(client: TestClient) -> None:
    """The single-label page surfaces a link to bulk upload so a reviewer who
    hits `/` can find the batch flow without reading the README."""
    response = client.get("/")
    assert "/batches" in response.text


def test_bulk_upload_redirects_to_batch_view() -> None:
    """Submitting N files spawns a batch worker and redirects to the existing
    `/batch/{batch_id}` shell that streams results via SSE."""
    from app.api.ui import _get_upload_evaluator
    from tests._fakes.evaluator import FakeEvaluator
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    fake = FakeEvaluator(
        [
            (0.0, _stub_disposition_envelope(0, disposition="pass")),
            (0.0, _stub_disposition_envelope(1, disposition="needs_review")),
        ]
    )
    app.dependency_overrides[_get_upload_evaluator] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/batches/upload",
        files=[
            ("labels", ("a.png", _PNG_1x1, "image/png")),
            ("labels", ("b.png", _PNG_1x1, "image/png")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/batch/")
    batch_id = location.removeprefix("/batch/")
    assert batch_id in app.state.batches


def test_bulk_upload_names_a_non_image_and_checks_the_rest() -> None:
    """A non-PNG/JPEG in the upload set is named as its own failed item and
    every other file is still checked.

    This asserted a 400 for the whole submission until 2026-09-16, defended on
    the grounds that scheduling the batch meant a batch that would "explode
    mid-stream". `docs/decisions.md#0020` removed that premise: the worker
    refuses an item it cannot check by name and carries on to the next one, so
    rejecting four good files because a fifth is a `.txt` now throws away work
    the product can do. Requirement R13 asks for the file to be named *and* the
    rest to run, and is a P0.
    """
    import time

    from app.api.ui import _get_upload_evaluator
    from tests._fakes.evaluator import FakeEvaluator
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    # One envelope: only the image is evaluated. The `.txt` never reaches the
    # evaluator, which is the point — nothing reports a verdict about it.
    fake = FakeEvaluator([(0.0, _stub_disposition_envelope(0, disposition="pass"))])
    app.dependency_overrides[_get_upload_evaluator] = lambda: fake

    with TestClient(app) as client:
        response = client.post(
            "/batches/upload",
            files=[
                ("labels", ("ok.png", _PNG_1x1, "image/png")),
                ("labels", ("oops.txt", b"not an image", "text/plain")),
            ],
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")

        # The worker runs as a task on the app's loop; poll its snapshot rather
        # than sleeping a fixed interval.
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            snapshot = client.get(f"/batches/{batch_id}").json()
            if all(item["state"] in ("ready", "failed") for item in snapshot["items"]):
                break
            time.sleep(0.02)

    items = {item["label_id"].split("-", 3)[-1]: item for item in snapshot["items"]}
    assert set(items) == {"ok.png", "oops.txt"}, snapshot

    # The bad file is named, with an instruction.
    bad = items["oops.txt"]
    assert bad["state"] == "failed", bad
    assert "oops.txt" in bad["failed_reason"]
    assert "PNG or JPEG" in bad["failed_reason"]
    assert bad["result"]["disposition"] == "needs_review"
    assert (
        bad["result"]["audit_trail"]["per_rule_trace"][0]["rule_id"]
        == "ENGINE.INPUT.LABEL_IMAGE_UNSUPPORTED"
    )

    # The rest of the batch has results.
    good = items["ok.png"]
    assert good["state"] == "ready", good
    assert good["result"]["disposition"] == "pass"
    assert good["failed_reason"] is None


def test_bulk_upload_rejects_a_submission_with_no_image_at_all() -> None:
    """When no file in the set is an image there is no batch to show a refusal
    in, so the submission is refused at the form, as an empty one is."""
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/batches/upload",
        files=[("labels", ("oops.txt", b"not an image", "text/plain"))],
    )
    assert response.status_code == 400
    assert "PNG or JPEG" in response.text


def test_bulk_upload_requires_at_least_one_file() -> None:
    """Submitting an empty form is a usage error, not an empty batch."""
    app = create_app()
    client = TestClient(app)
    response = client.post("/batches/upload", files=[])
    assert response.status_code in (400, 422)
