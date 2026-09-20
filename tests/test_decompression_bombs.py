"""Decompression bombs: a small file that declares an enormous image.

A byte cap cannot catch one, because the file really is small. A few hundred
bytes of PNG can declare a 30,000 x 30,000 canvas; the cost lands at decode,
where that is 900 million pixels.

What the service did before this: `Image.MAX_IMAGE_PIXELS` was never set, so
Pillow's own ceiling sat at its default and nothing acted on it. Worse,
`app/vision/quality.py::_decode_grayscale` catches bare `Exception`, so a bomb
Pillow *did* flag came back to the user as "needs a better photo" — which tells
them to re-photograph a label that was never the problem, and hides the fact
that the service was attacked. The reader's own `MAX_EDGE_PX = 1600` thumbnail
is no protection either: it shrinks the image after decoding, which is where the
memory is spent.

The guard reads the pixel count out of the file's header and refuses before any
decode, so a bomb costs the header and nothing else.
"""

from __future__ import annotations

import io
import json
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import limits
from app.deps import reset_vision_extractor
from app.main import app
from tests._fakes.vision import FakeVisionExtractor


def _bomb_png(width: int, height: int) -> bytes:
    """A real, valid PNG whose header declares `width` x `height`.

    Built by writing a 1x1 image and rewriting the IHDR dimensions with a
    correct CRC, so the file stays a well-formed PNG that any decoder will
    believe — which is the whole point. It stays a few hundred bytes.
    """
    buf = io.BytesIO()
    Image.new("L", (1, 1), 0).save(buf, format="PNG")
    raw = bytearray(buf.getvalue())
    # 8-byte signature, then the IHDR chunk: 4 length, 4 type, 13 data, 4 CRC.
    ihdr_start = 8 + 4
    data_start = ihdr_start + 4
    raw[data_start : data_start + 8] = struct.pack(">II", width, height)
    chunk = bytes(raw[ihdr_start : data_start + 13])
    raw[data_start + 13 : data_start + 17] = struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    return bytes(raw)


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


def test_the_bomb_fixture_really_is_small_and_really_declares_a_huge_image() -> None:
    """Without this the rest of the file could be testing nothing: a fixture
    that is merely large would be caught by the byte cap instead."""
    bomb = _bomb_png(30_000, 30_000)
    assert len(bomb) < limits.MAX_UPLOAD_BYTES
    assert limits.declared_pixels(bomb) == 30_000 * 30_000


def test_the_pixel_ceiling_is_stated_and_acted_on() -> None:
    """Pillow's default ceiling only warns. Ours is set explicitly and refused
    on, and it sits above any camera a real submission comes from."""
    assert Image.MAX_IMAGE_PIXELS == limits.MAX_IMAGE_PIXELS
    assert limits.MAX_IMAGE_PIXELS >= 48_000_000


def test_a_real_photograph_is_not_mistaken_for_a_bomb() -> None:
    """The guard has to let through what the service exists to read."""
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), (200, 180, 160)).save(buf, format="JPEG")
    assert limits.declared_pixels(buf.getvalue()) < limits.MAX_IMAGE_PIXELS


def test_post_labels_refuses_a_bomb_with_its_own_reason_code(client, deterministic_seams) -> None:
    """Its own code, not the unsupported-file code and not a photo-quality
    finding: the operator reading the logs needs to see that a bomb arrived."""
    response = client.post(
        "/labels",
        files={
            "application": (
                "a.json",
                json.dumps({"application_id": "A-001", "evaluation_id": "EV-001"}),
                "application/json",
            ),
            "label": ("bomb.png", _bomb_png(30_000, 30_000), "image/png"),
        },
    )
    assert response.status_code == 413
    body = response.json()
    assert body["error_kind"] == "rejected_input"
    assert body["reason_code"] == "ENGINE.INPUT.IMAGE_TOO_MANY_PIXELS"
    assert "bomb.png" in json.dumps(body)


def test_the_upload_page_refuses_a_bomb_and_does_not_blame_the_photograph(
    client, deterministic_seams
) -> None:
    """The failure this replaces. A bomb answered as "needs a better photo"
    sends the user off to re-photograph a label that was never at fault."""
    response = client.post(
        "/",
        files={"labels": ("bomb.png", _bomb_png(30_000, 30_000), "image/png")},
        data={"beverage_type": "distilled_spirits"},
    )
    assert response.status_code == 413
    assert "bomb.png" in response.text
    assert "better photo" not in response.text.lower()


def test_the_upload_form_names_the_bomb_among_several(client, deterministic_seams) -> None:
    response = client.post(
        "/",
        files=[
            ("labels", ("ok.png", _bomb_png(800, 600), "image/png")),
            ("labels", ("bomb.png", _bomb_png(30_000, 30_000), "image/png")),
        ],
        data={"beverage_type": "distilled_spirits"},
    )
    assert response.status_code == 413
    assert "bomb.png" in response.text
