"""The result page shows every photograph the reviewer sent, and says which.

The fault this file guards: the page rendered exactly one `<img>`, always the
front. A label's government warning is usually printed on the back, so a
reviewer reading a warning finding was looking at a photograph that does not
carry the warning — a page that reads as broken to the person it is meant to
convince, whatever the envelope underneath it says.

The store has held every face since the sample and upload routes started
sending them. What was missing was anything asking it what it had:
`UploadImageStore.faces()` had no caller at all.

The caller is now `GET /labels/{eval_id}/faces`, which the results island asks
before it renders any photograph (`docs/decisions.md#0045`). The guard is
therefore in two halves, and this is the server's: every face the check was
made from is offered, each with a caption of its own and a URL that really
loads. The other half — one `<img>` per offered face, each with alt text a
screen reader user can tell apart — is
`frontend/src/components/LabelResult.test.tsx`, because nothing about it
reaches the server any more.
"""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.ui import _get_upload_evaluator
from app.api.ui.images import UploadImageStore, _get_image_store
from app.main import create_app
from tests._fakes.evaluator import FakeEvaluator
from tests.conftest import _stub_disposition_envelope


def _png(colour: tuple[int, int, int]) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1, 1), color=colour).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path):
    app = create_app()
    app.state.envelope = _stub_disposition_envelope(7, disposition="needs_review")
    evaluator = FakeEvaluator([(0.0, app.state.envelope)])
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path)
    # Entered as a context manager: the check runs as a background task on the
    # app's own loop, and the images are filed as each result lands.
    with TestClient(app) as entered:
        yield entered


def _await_batch(client: TestClient, response) -> None:
    """Wait for the check the POST started to finish."""
    assert response.status_code == 303, response.text
    batch_id = response.headers["location"].removeprefix("/batch/")
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        items = client.get(f"/batches/{batch_id}").json()["items"]
        if items and all(item["state"] in ("ready", "failed") for item in items):
            return
        time.sleep(0.02)
    raise AssertionError(f"batch {batch_id} did not finish")


def _check_two_faces(client: TestClient) -> list[dict]:
    """Check one label with a front and a back; return the faces offered."""
    _await_batch(
        client,
        client.post(
            "/",
            files=[
                ("labels", ("lucy-front.png", _png((0, 0, 0)), "image/png")),
                ("labels", ("lucy-back.png", _png((255, 255, 255)), "image/png")),
            ],
            data={"beverage_type": "distilled_spirits"},
            follow_redirects=False,
        ),
    )
    evaluation_id = client.app.state.envelope.evaluation_id
    return client.get(f"/labels/{evaluation_id}/faces").json()["faces"]


def test_a_front_and_a_back_are_both_offered(client: TestClient) -> None:
    evaluation_id = client.app.state.envelope.evaluation_id
    sources = [face["url"] for face in _check_two_faces(client)]
    assert f"/labels/{evaluation_id}/image?face=front" in sources
    assert f"/labels/{evaluation_id}/image?face=back" in sources


def test_both_photographs_really_load(client: TestClient) -> None:
    """A URL the page renders that 404s is the same broken page with extra
    steps, and two URLs serving one photograph is the original fault wearing a
    second `<img>`."""
    fetched = {}
    for face in _check_two_faces(client):
        got = client.get(face["url"])
        assert got.status_code == 200, f"{face['url']} did not load"
        fetched[face["url"]] = got.content
    assert len(set(fetched.values())) == 2, "both figures showed the same photograph"


def test_each_photograph_is_named_so_a_reviewer_can_tell_them_apart(
    client: TestClient,
) -> None:
    """The caption is what the page's visible label and its alt text are both
    built from, so two faces sharing one caption is two figures a reviewer
    cannot tell apart."""
    captions = [face["caption"] for face in _check_two_faces(client)]
    assert captions == ["Front", "Back"], captions


def test_a_one_faced_label_offers_one_photograph(client: TestClient) -> None:
    """Unchanged for the reviewer who sends a front and nothing else."""
    _await_batch(
        client,
        client.post(
            "/",
            files={"labels": ("front.png", _png((0, 0, 0)), "image/png")},
            data={"beverage_type": "distilled_spirits"},
            follow_redirects=False,
        ),
    )
    evaluation_id = client.app.state.envelope.evaluation_id
    faces = client.get(f"/labels/{evaluation_id}/faces").json()["faces"]
    assert [face["url"] for face in faces] == [f"/labels/{evaluation_id}/image?face=front"]


def test_a_sample_with_a_back_offers_its_back(tmp_path: Path) -> None:
    """The shipped samples are the path a reviewer with no labels takes, and
    the bourbon's warning is on its back."""
    app = create_app()
    envelope = _stub_disposition_envelope(11, disposition="needs_review")
    evaluator = FakeEvaluator([(0.0, envelope)])
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path)

    with TestClient(app) as client:
        _await_batch(client, client.post("/samples/ttb-26231001000662", follow_redirects=False))
        faces = client.get(f"/labels/{envelope.evaluation_id}/faces").json()["faces"]

    sources = [face["url"] for face in faces]
    assert f"/labels/{envelope.evaluation_id}/image?face=back" in sources
