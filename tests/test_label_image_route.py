"""Reviewer UI must display the label image after an upload.

  GET /labels/{eval_id}/image     — returns the bytes uploaded via
                                     POST /. Bytes are cached in-process
                                     keyed on the synthesized evaluation_id
                                     so a follow-up GET against the rendered
                                     page sees the same image.

Returns 404 for unknown ids; sets Content-Type: image/png or image/jpeg.
"""
from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


def _png_1x1() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


def test_upload_image_round_trips():
    """An upload's bytes must be retrievable via /labels/{eval_id}/image
    so the rendered template can display them."""
    from app.api.ui import _get_upload_evaluator
    from tests._fakes.evaluator import FakeEvaluator
    from tests.conftest import _stub_disposition_envelope

    app = create_app()
    env = _stub_disposition_envelope(42, disposition="pass")
    fake = FakeEvaluator([(0.0, env)])
    app.dependency_overrides[_get_upload_evaluator] = lambda: fake
    client = TestClient(app)

    png = _png_1x1()
    response = client.post(
        "/", files={"label": ("upload.png", png, "image/png")}
    )
    assert response.status_code == 200
    # The shell must reference the image route by the synthesized eval id.
    assert f"/labels/{env.evaluation_id}/image" in response.text

    # The bytes round-trip — the cache lookup returns the exact upload.
    img = client.get(f"/labels/{env.evaluation_id}/image")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert img.content == png


def test_upload_image_404_on_unknown_eval_id():
    client = TestClient(create_app())
    response = client.get("/labels/no-such-id/image")
    assert response.status_code == 404
