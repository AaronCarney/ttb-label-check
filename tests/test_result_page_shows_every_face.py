"""The result page shows every photograph the reviewer sent, and says which.

The fault this file guards: the page rendered exactly one `<img>`, always the
front. A label's government warning is usually printed on the back, so a
reviewer reading a warning finding was looking at a photograph that does not
carry the warning — a page that reads as broken to the person it is meant to
convince, whatever the envelope underneath it says.

The store has held every face since the sample and upload routes started
sending them. What was missing was anything asking it what it had:
`UploadImageStore.faces()` had no caller at all.
"""

from __future__ import annotations

import re
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
def client(tmp_path: Path) -> TestClient:
    app = create_app()
    app.state.envelope = _stub_disposition_envelope(7, disposition="needs_review")
    app.dependency_overrides[_get_upload_evaluator] = lambda: FakeEvaluator(
        [(0.0, app.state.envelope)]
    )
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path)
    return TestClient(app)


def _image_sources(html: str) -> list[str]:
    return re.findall(r'<img src="([^"]+)"', html)


def test_a_front_and_a_back_both_appear_on_the_page(client: TestClient) -> None:
    response = client.post(
        "/",
        files={
            "label": ("front.png", _png((0, 0, 0)), "image/png"),
            "label_back": ("back.png", _png((255, 255, 255)), "image/png"),
        },
    )
    assert response.status_code == 200

    evaluation_id = client.app.state.envelope.evaluation_id
    sources = _image_sources(response.text)
    assert f"/labels/{evaluation_id}/image?face=front" in sources
    assert f"/labels/{evaluation_id}/image?face=back" in sources


def test_both_photographs_really_load(client: TestClient) -> None:
    """A URL on the page that 404s is the same broken page with extra steps."""
    front, back = _png((0, 0, 0)), _png((255, 255, 255))
    response = client.post(
        "/",
        files={
            "label": ("front.png", front, "image/png"),
            "label_back": ("back.png", back, "image/png"),
        },
    )

    fetched = {}
    for source in _image_sources(response.text):
        got = client.get(source)
        assert got.status_code == 200, f"{source} did not load"
        fetched[source] = got.content
    assert len(set(fetched.values())) == 2, "both figures showed the same photograph"


def test_each_photograph_is_named_so_a_reviewer_can_tell_them_apart(
    client: TestClient,
) -> None:
    response = client.post(
        "/",
        files={
            "label": ("front.png", _png((0, 0, 0)), "image/png"),
            "label_back": ("back.png", _png((255, 255, 255)), "image/png"),
        },
    )
    assert "Front" in response.text and "Back" in response.text


def test_the_alt_text_says_which_face_each_image_is(client: TestClient) -> None:
    """Two images described identically are two images a screen reader user
    cannot tell apart (NFR-3)."""
    response = client.post(
        "/",
        files={
            "label": ("front.png", _png((0, 0, 0)), "image/png"),
            "label_back": ("back.png", _png((255, 255, 255)), "image/png"),
        },
    )
    alts = re.findall(r'<img [^>]*alt="([^"]+)"', response.text)
    assert len(alts) == 2
    assert len(set(alts)) == 2, f"both images described the same way: {alts}"


def test_a_one_faced_label_shows_one_photograph(client: TestClient) -> None:
    """Unchanged for the reviewer who sends a front and nothing else."""
    response = client.post("/", files={"label": ("front.png", _png((0, 0, 0)), "image/png")})

    sources = _image_sources(response.text)
    assert len(sources) == 1
    evaluation_id = client.app.state.envelope.evaluation_id
    assert sources[0] == f"/labels/{evaluation_id}/image?face=front"


def test_a_sample_with_a_back_shows_its_back(tmp_path: Path) -> None:
    """The shipped samples are the path a reviewer with no labels takes, and
    the bourbon's warning is on its back."""
    app = create_app()
    envelope = _stub_disposition_envelope(11, disposition="needs_review")
    app.dependency_overrides[_get_upload_evaluator] = lambda: FakeEvaluator([(0.0, envelope)])
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path)
    client = TestClient(app)

    response = client.post("/samples/ttb-26231001000662")
    assert response.status_code == 200
    sources = _image_sources(response.text)
    assert f"/labels/{envelope.evaluation_id}/image?face=back" in sources
