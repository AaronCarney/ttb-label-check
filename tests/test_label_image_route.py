"""The label image a result page shows is still there when the page asks for it.

  GET /labels/{eval_id}/image  — the bytes uploaded by POST /, served back
                                 under the evaluation id the result envelope
                                 carries, so the `<img>` the page renders
                                 resolves.

`POST /` answers with a redirect to the results page, and that page is a shell:
the image URL reaches the browser over the result stream rather than in the
HTML. So a test here asks the store's own routes whether an image is there —
`/labels/{eval_id}/faces` for which photographs exist and
`/labels/{eval_id}/image` for the bytes — instead of reading a page.

The route used to read from a 64-entry dictionary held in one process's memory,
which meant a result page's own image stopped loading after 64 further uploads,
after a restart, and on any worker but the one that took the upload. The three
tests named for those losses are the guard on that; see
`docs/decisions.md#0018`.
"""

from __future__ import annotations

import os
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


def _png_1x1() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


def _app_storing_into(root: Path, envelopes) -> TestClient:
    """The real app, with a stubbed evaluator and a store of the test's own.

    `envelopes` is what the stubbed evaluator returns, in order; each one's
    `evaluation_id` is the id the upload's image is filed under.
    """
    app = create_app()
    # One evaluator for the whole client, not one per request: a fresh
    # FakeEvaluator would restart its plan and hand every upload the first
    # envelope, which would file 65 uploads under one id and make the
    # eviction test below pass without testing anything.
    evaluator = FakeEvaluator([(0.0, envelope) for envelope in envelopes])
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(root)
    return TestClient(app)


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


def _upload(client: TestClient, body: bytes, name: str = "upload.png") -> dict:
    """Check one label and wait for the batch it started to finish.

    The image is filed by the worker as each result lands, so a test that reads
    it back has to wait for the worker rather than for the POST. The client
    must be entered as a context manager, or the worker's task dies with the
    request's event loop.
    """
    response = client.post(
        "/",
        files={"labels": (name, body, "image/png")},
        data={"beverage_type": "distilled_spirits"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    batch_id = response.headers["location"].removeprefix("/batch/")
    return _wait_for_batch(client, batch_id)


# ---------------------------------------------------------------------------
# The round trip, through the store the running app actually uses
# ---------------------------------------------------------------------------


def test_upload_image_round_trips():
    """An upload's bytes are retrievable at the URL the page renders.

    No store is overridden here, so this is the one test that proves the
    default location the app ships with can be written to and read back.
    """
    app = create_app()
    env = _stub_disposition_envelope(42, disposition="pass")
    app.dependency_overrides[_get_upload_evaluator] = lambda: FakeEvaluator([(0.0, env)])

    png = _png_1x1()
    with TestClient(app) as client:
        _upload(client, png)

        # The route the results page asks names the image route by the id the
        # envelope carries, which is what makes the rendered `<img>` resolve.
        faces = client.get(f"/labels/{env.evaluation_id}/faces").json()["faces"]
        assert [face["url"] for face in faces] == [f"/labels/{env.evaluation_id}/image?face=front"]

        img = client.get(f"/labels/{env.evaluation_id}/image")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"
        assert img.content == png


def test_upload_image_404_on_unknown_eval_id():
    client = TestClient(create_app())
    response = client.get("/labels/no-such-id/image")
    assert response.status_code == 404


def test_a_jpeg_upload_comes_back_as_a_jpeg(tmp_path: Path):
    """The media type survives the round trip, so the browser is not told a
    JPEG is a PNG."""
    env = _stub_disposition_envelope(7, disposition="pass")

    buf = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(buf, "JPEG")
    jpeg = buf.getvalue()

    with _app_storing_into(tmp_path, [env]) as client:
        _upload(client, jpeg, name="upload.jpg")
        img = client.get(f"/labels/{env.evaluation_id}/image")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/jpeg"
        assert img.content == jpeg


# ---------------------------------------------------------------------------
# The three losses the old in-memory cache had
# ---------------------------------------------------------------------------


def test_the_image_survives_sixty_four_further_uploads(tmp_path: Path):
    """The cache this replaced held 64 entries and evicted the oldest, so the
    65th upload took the first one's image away from a page still open on it."""
    first = _stub_disposition_envelope(0, disposition="pass")
    later = [_stub_disposition_envelope(i, disposition="pass") for i in range(1, 65)]

    png = _png_1x1()
    with _app_storing_into(tmp_path, [first, *later]) as client:
        _upload(client, png)
        for _ in later:
            _upload(client, png)

        still_there = client.get(f"/labels/{first.evaluation_id}/image")
        assert still_there.status_code == 200, "64 further uploads evicted the first image"
        assert still_there.content == png


def test_the_image_outlives_the_process_that_received_it(tmp_path: Path):
    """A restart loses every object in memory and no file on disk. The second
    client here shares nothing with the first but the directory."""
    env = _stub_disposition_envelope(11, disposition="pass")
    png = _png_1x1()
    with _app_storing_into(tmp_path, [env]) as client:
        _upload(client, png)

    after_restart = _app_storing_into(tmp_path, [])
    img = after_restart.get(f"/labels/{env.evaluation_id}/image")
    assert img.status_code == 200, "the image did not survive the process that took it"
    assert img.content == png


def test_a_second_worker_serves_an_image_the_first_one_received(tmp_path: Path):
    """Two workers of one deployment answer in turn, so the worker that serves
    the result page is usually not the one that took the upload."""
    env = _stub_disposition_envelope(12, disposition="pass")
    png = _png_1x1()

    worker_one = UploadImageStore(tmp_path)
    worker_two = UploadImageStore(tmp_path)
    worker_one.put(env.evaluation_id, "image/png", png)

    assert worker_two.get(env.evaluation_id) == ("image/png", png)


# ---------------------------------------------------------------------------
# The store's own edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "eval_id",
    ["../secrets", "..", "a/b", "/etc/passwd", "", "x" * 129],
)
def test_an_evaluation_id_that_is_not_one_reads_nothing(tmp_path: Path, eval_id: str):
    """The id arrives from a URL path. Anything that could name a file outside
    the store, or is not an id at all, is answered as no image rather than
    being joined to the directory."""
    store = UploadImageStore(tmp_path)
    assert store.get(eval_id) is None
    with pytest.raises(ValueError):
        store.put(eval_id, "image/png", _png_1x1())


def test_the_route_turns_an_id_it_will_not_store_under_into_a_404(tmp_path: Path):
    """The guard has to fire at the route, not only in the store.

    A path separator never reaches the route at all — the router matches one
    segment, so `/labels/../x/image` is simply not this route — but a dot is a
    segment character and reaches the handler. The body proves this 404 is the
    handler's answer rather than the router's, which reads `{"detail": "Not
    Found"}`.
    """
    client = _app_storing_into(tmp_path, [])

    response = client.get("/labels/..%2E%2E/image")

    assert response.status_code == 404
    assert "no front image for evaluation" in response.text


def test_an_image_older_than_the_retention_window_is_dropped(tmp_path: Path):
    """The bound on growth is age, not a count of entries: a count is what put
    a live page's own image at risk. A write sweeps what has expired."""
    from app.api.ui import images as images_module

    store = UploadImageStore(tmp_path)
    store.put("ev-old", "image/png", _png_1x1())
    stale = time.time() - images_module._RETENTION_SECONDS - 60
    os.utime(tmp_path / "ev-old.front.png", (stale, stale))

    store.put("ev-new", "image/png", _png_1x1())

    assert store.get("ev-old") is None
    assert store.get("ev-new") is not None


def test_a_fresh_image_is_not_dropped_by_the_sweep(tmp_path: Path):
    store = UploadImageStore(tmp_path)
    store.put("ev-one", "image/png", _png_1x1())
    store.put("ev-two", "image/png", _png_1x1())
    assert store.get("ev-one") is not None
