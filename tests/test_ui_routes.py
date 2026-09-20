"""The page-shell GET routes, the StaticFiles mount, and `POST /`.

There is one way in and one place results arrive: `GET /` serves the form,
`POST /` starts the check and redirects to `GET /batch/{batch_id}`, which
streams the results. The bulk-upload page that used to sit at `/batches` is a
redirect to `/` (`docs/decisions.md#0045`).
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_settings
from app.config import Settings
from app.main import create_app

# A tiny valid PNG (1x1 black pixel), used wherever a real image is needed.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


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


# ---------------------------------------------------------------------------
# The page shells
# ---------------------------------------------------------------------------


def test_entry_page_is_the_form(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="labels"' in response.text
    assert "multiple" in response.text
    assert 'method="post"' in response.text or 'method="POST"' in response.text
    # The noscript fallback, for a browser with JavaScript turned off.
    assert "<noscript>" in response.text
    assert "POST /labels" in response.text


def test_entry_page_mounts_no_island(client: TestClient) -> None:
    """Nothing on the form has a result to render, so it ships no JavaScript.
    The island belongs to the page where a check is watched."""
    response = client.get("/")
    assert 'id="root"' not in response.text
    assert "/static/island/app.js" not in response.text


def test_results_page_shell(client: TestClient) -> None:
    response = client.get("/batch/abc-123")
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert 'data-batch-id="abc-123"' in response.text
    assert "/static/island/app.js" in response.text


def test_the_old_bulk_page_redirects_to_the_one_form(client: TestClient) -> None:
    """`/batches` was the second way in. It is the URL the deployed service has
    been handing out, so it redirects rather than 404s."""
    response = client.get("/batches", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "/"


def test_static_island_mount(client: TestClient) -> None:
    """The StaticFiles mount serves files under app/ui/static/. The sentinel is
    /static/island/style.css, a file the build itself emits — Vite's emptyOutDir
    wipes any placeholder on every build, so a placeholder cannot be used."""
    response = client.get("/static/island/style.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_dev_mode_off_by_default(client: TestClient) -> None:
    """RawJSONDrawer reads body[data-dev-mode] — default is '0'."""
    response = client.get("/batch/abc-123")
    assert 'data-dev-mode="0"' in response.text


def test_dev_mode_on_when_settings_enabled(dev_client: TestClient) -> None:
    """When DEV_MODE=1, the body attribute lets the React island render the
    RawJSONDrawer. Both shells honour it."""
    assert 'data-dev-mode="1"' in dev_client.get("/").text
    assert 'data-dev-mode="1"' in dev_client.get("/batch/abc-123").text


def test_uswds_skip_link_present(client: TestClient) -> None:
    """NFR-3 keyboard-operable end-to-end (WCAG 2.1.1): the 'Skip to main
    content' link must be the first focusable element on every page."""
    for path in ("/", "/batch/abc-123"):
        response = client.get(path)
        assert 'class="skip-link"' in response.text, path
        assert "Skip to main content" in response.text, path


def test_entry_page_reaches_the_sample_pack(client: TestClient) -> None:
    """A reviewer with no labels of their own has to be able to get to the
    pack, and the form is now the only page that can carry the way there."""
    response = client.get("/")
    assert "/batches/sample.zip" in response.text


# ---------------------------------------------------------------------------
# POST / — the one way a check starts
# ---------------------------------------------------------------------------


def _wait_for_batch(client: TestClient, batch_id: str, *, timeout: float = 10.0) -> dict:
    """Poll the batch snapshot until every item has finished."""
    deadline = time.monotonic() + timeout
    snapshot = client.get(f"/batches/{batch_id}").json()
    while time.monotonic() < deadline:
        if all(item["state"] in ("ready", "failed") for item in snapshot["items"]):
            return snapshot
        time.sleep(0.02)
        snapshot = client.get(f"/batches/{batch_id}").json()
    return snapshot


def test_one_label_starts_a_batch_and_redirects() -> None:
    """One label is a batch of one. It takes the same route, starts the same
    worker and lands on the same results page as three hundred."""
    from app.api.ui import _get_upload_evaluator
    from tests._fakes.evaluator import FakeEvaluator
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    fake = FakeEvaluator([(0.0, _stub_disposition_envelope(99, disposition="pass"))])
    app.dependency_overrides[_get_upload_evaluator] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/",
        files={"labels": ("upload.png", _PNG_1x1, "image/png")},
        data={"beverage_type": "distilled_spirits"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/batch/")
    assert location.removeprefix("/batch/") in app.state.batches


def test_several_labels_start_one_batch() -> None:
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
        "/",
        files=[
            ("labels", ("a.png", _PNG_1x1, "image/png")),
            ("labels", ("b.png", _PNG_1x1, "image/png")),
        ],
        data={"beverage_type": "wine"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    batch_id = response.headers["location"].removeprefix("/batch/")
    assert batch_id in app.state.batches


def test_a_non_image_is_named_and_the_rest_are_checked() -> None:
    """A non-PNG/JPEG in the upload set is named as its own failed item and
    every other file is still checked.

    This used to assert a 400 for the whole submission, defended on the grounds
    that scheduling the batch meant a batch that would "explode mid-stream".
    `docs/decisions.md#0020` removed that premise: the worker refuses an item it
    cannot check by name and carries on to the next one, so rejecting four good
    files because a fifth is a `.txt` now throws away work the product can do.
    Requirement R13 asks for the file to be named *and* the rest to run, and is
    a P0.
    """
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
            "/",
            files=[
                ("labels", ("ok.png", _PNG_1x1, "image/png")),
                ("labels", ("oops.txt", b"not an image", "text/plain")),
            ],
            data={"beverage_type": "wine"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")
        snapshot = _wait_for_batch(client, batch_id)

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


def test_a_submission_with_no_image_at_all_is_refused() -> None:
    """When no file in the set is an image there is no batch to show a refusal
    in, so the submission is refused at the form, as an empty one is."""
    client = TestClient(create_app())
    response = client.post(
        "/",
        files=[("labels", ("oops.txt", b"not an image", "text/plain"))],
        data={"beverage_type": "wine"},
    )
    assert response.status_code == 400
    assert "PNG or JPEG" in response.text


def test_a_refusal_comes_back_on_the_form_with_what_was_typed() -> None:
    """The reviewer's ten fields return with the banner, so a mis-typed field
    is one correction away rather than ten."""
    client = TestClient(create_app())
    response = client.post(
        "/",
        files=[("labels", ("oops.txt", b"not an image", "text/plain"))],
        data={"beverage_type": "wine", "brand_name": "Stone's Throw"},
    )
    assert response.status_code == 400
    assert 'role="alert"' in response.text
    assert "Stone&#39;s Throw" in response.text or "Stone's Throw" in response.text
    assert 'value="distilled_spirits"' in response.text  # the form itself came back


def test_submitting_no_file_at_all_is_a_422(client: TestClient) -> None:
    """FastAPI's File(...) requirement produces a 422 when the part is missing."""
    response = client.post("/", files={})
    assert response.status_code == 422
