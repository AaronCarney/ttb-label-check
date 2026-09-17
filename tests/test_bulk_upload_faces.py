"""Two files that are two faces of one label become one label, not two.

The fault this file guards: the batch upload built one label per uploaded file,
so a bourbon whose government warning is printed on the back came back twice —
once as a front that fails the warning check, once as a back with no brand and
no class. Two wrong answers about one product, on the path that exists to show
volume.

The pairing convention is the one the product already emits: `/batches/sample.zip`
names its entries `{ttbid}-front.jpg`. A stem ending `-front` or `-back` is half
of a label; anything else is a label on its own, exactly as before.

No reader and no rules here. The evaluator is a double that records the labels it
was handed, because what this route decides is what a label *is*, and the answer
is visible at the evaluator's door.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import httpx
import pytest

from app.schemas.application import Application
from app.schemas.label import Label

# A real 1x1 PNG. The route reads an upload's own first bytes to decide its
# media type, so the file has to be one; nothing here looks at the pixels.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)
# A second, visibly different PNG, so a test can tell which bytes landed on
# which face rather than trusting the tag alone.
_PNG_1x1_OTHER = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c489000000017352474200aece1ce90000000c49444154789c63"
    "6060606000000004000180fe8f8d0000000049454e44ae426082"
)


class _RecordingEvaluator:
    """Accepts anything, records every label it was asked about."""

    def __init__(self) -> None:
        self.labels: list[Label] = []

    async def evaluate(self, application: Application, label: Label):
        from tests.conftest import _stub_disposition_envelope

        self.labels.append(label)
        return _stub_disposition_envelope(len(self.labels) - 1)


async def _upload(files: list[tuple[str, tuple[str, bytes, str]]]) -> list[Label]:
    """Post `files` to the batch upload route and return the labels the
    evaluator was handed, in the order the worker asked about them."""
    from app.api.ui import _get_upload_evaluator
    from app.main import create_app

    app = create_app()
    evaluator = _RecordingEvaluator()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/batches/upload", files=files)
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")
        async with client.stream("GET", f"/batches/{batch_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if "stream-end" in line:
                    break
    # The worker is spawned as a background task; give a cancelled one no
    # chance to be mistaken for an empty result.
    await asyncio.sleep(0)
    return evaluator.labels


def _file(name: str, body: bytes = _PNG_1x1) -> tuple[str, tuple[str, bytes, str]]:
    return ("labels", (name, body, "image/png"))


@pytest.mark.asyncio
async def test_front_and_back_of_one_stem_become_one_two_faced_label() -> None:
    labels = await _upload([_file("26231001000662-front.png"), _file("26231001000662-back.png")])

    assert len(labels) == 1, f"expected one label, got {[label.label_id for label in labels]}"
    assert tuple(face.face_tag for face in labels[0].faces) == ("front", "back")


@pytest.mark.asyncio
async def test_the_paired_label_is_named_for_the_stem_the_two_files_share() -> None:
    """A reviewer reading the results has to see which of their files a row is
    about, and for a pair that is the name without the face suffix."""
    labels = await _upload([_file("26231001000662-front.png"), _file("26231001000662-back.png")])

    assert labels[0].label_id.endswith("26231001000662")
    assert "front" not in labels[0].label_id and "back" not in labels[0].label_id


@pytest.mark.asyncio
async def test_each_face_carries_the_bytes_of_its_own_file() -> None:
    """Pairing must not hand the same photograph to the reader twice."""
    labels = await _upload(
        [
            _file("lucy-front.png", _PNG_1x1),
            _file("lucy-back.png", _PNG_1x1_OTHER),
        ]
    )

    by_tag = {face.face_tag: face.image_bytes for face in labels[0].faces}
    assert by_tag["front"] == _PNG_1x1
    assert by_tag["back"] == _PNG_1x1_OTHER


@pytest.mark.asyncio
async def test_the_front_comes_first_however_the_files_were_picked() -> None:
    """A file picker returns whatever order the filesystem gave it, and the
    quality gate stops at the first unusable face, so face order must be the
    label's own order rather than the upload's."""
    labels = await _upload([_file("lucy-back.png"), _file("lucy-front.png")])

    assert len(labels) == 1
    assert tuple(face.face_tag for face in labels[0].faces) == ("front", "back")


@pytest.mark.asyncio
async def test_the_suffix_is_read_whatever_its_case() -> None:
    labels = await _upload([_file("LUCY-FRONT.PNG"), _file("lucy-Back.png")])

    assert len(labels) == 1
    assert tuple(face.face_tag for face in labels[0].faces) == ("front", "back")


@pytest.mark.asyncio
async def test_a_file_with_no_face_suffix_is_a_label_on_its_own() -> None:
    """Unchanged behaviour for every reviewer who names their files anything
    else: one file, one label, one front."""
    labels = await _upload([_file("label-a.png"), _file("label-b.png")])

    assert len(labels) == 2
    for label in labels:
        assert tuple(face.face_tag for face in label.faces) == ("front",)


@pytest.mark.asyncio
async def test_a_back_with_no_front_is_a_one_faced_label_tagged_back() -> None:
    """The reviewer sent a back; saying it is a front would make the reader
    report that a back label has no brand on it."""
    labels = await _upload([_file("lucy-back.png")])

    assert len(labels) == 1
    assert tuple(face.face_tag for face in labels[0].faces) == ("back",)


@pytest.mark.asyncio
async def test_a_front_with_no_back_is_still_one_label() -> None:
    labels = await _upload([_file("lucy-front.png")])

    assert len(labels) == 1
    assert tuple(face.face_tag for face in labels[0].faces) == ("front",)


@pytest.mark.asyncio
async def test_two_pairs_are_two_labels_and_do_not_cross() -> None:
    labels = await _upload(
        [
            _file("alpha-front.png", _PNG_1x1),
            _file("beta-front.png", _PNG_1x1_OTHER),
            _file("alpha-back.png", _PNG_1x1_OTHER),
            _file("beta-back.png", _PNG_1x1),
        ]
    )

    assert len(labels) == 2
    by_stem = {label.label_id.rsplit("-", 1)[-1]: label for label in labels}
    assert set(by_stem) == {"alpha", "beta"}
    alpha = {face.face_tag: face.image_bytes for face in by_stem["alpha"].faces}
    assert alpha == {"front": _PNG_1x1, "back": _PNG_1x1_OTHER}


@pytest.mark.asyncio
async def test_a_second_front_for_one_stem_is_its_own_label_rather_than_dropped() -> None:
    """Two files claiming the same face of the same label is a reviewer's
    mistake, and losing one silently is the worst answer to it: the extra is
    checked as a label of its own, so every uploaded file has a result."""
    labels = await _upload(
        [
            _file("lucy-front.png", _PNG_1x1),
            _file("lucy-front.png", _PNG_1x1_OTHER),
            _file("lucy-back.png", _PNG_1x1),
        ]
    )

    assert len(labels) == 2
    faces_sent = sorted(len(label.faces) for label in labels)
    assert faces_sent == [1, 2]


@pytest.mark.asyncio
async def test_an_unreadable_half_does_not_take_its_partner_down() -> None:
    """A file that is not an image is refused by name (R13). Its partner is a
    real photograph of a real label and is still checked, on its own."""
    from app.api.ui import _get_upload_evaluator
    from app.main import create_app

    app = create_app()
    evaluator = _RecordingEvaluator()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/batches/upload",
            files=[
                _file("lucy-front.png"),
                ("labels", ("lucy-back.png", b"not an image at all", "image/png")),
            ],
        )
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")
        async with client.stream("GET", f"/batches/{batch_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if "stream-end" in line:
                    break

    assert len(evaluator.labels) == 1
    assert tuple(face.face_tag for face in evaluator.labels[0].faces) == ("front",)
    in_flight = app.state.batches[batch_id]
    refused = [item for item in in_flight.items if "back" in item.label_id]
    assert refused, "the unreadable back must still appear as its own row"


# ---------------------------------------------------------------------------
# The sample zip has to carry the convention it teaches.
# ---------------------------------------------------------------------------


def test_sample_zip_ships_both_faces_of_a_label_that_has_two() -> None:
    """A zip of fronts cannot demonstrate a back-label warning, and the zip is
    the route a reviewer without labels of their own takes into the batch."""
    from fastapi.testclient import TestClient

    from app.api.ui import samples
    from app.main import create_app

    client = TestClient(create_app())
    response = client.get(f"/batches/sample.zip?n={len(samples._load_sample_ttbids())}")
    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()

    backs = [name for name in names if "-back." in name]
    assert backs, "no back face in the sample zip"
    for back in backs:
        assert back.replace("-back.", "-front.") in names, f"{back} arrived without its front"


def test_sample_zip_n_counts_labels_not_files() -> None:
    """`n` has always meant labels. With two faces per label it has to keep
    meaning that, or a reviewer asking for ten gets five."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    response = client.get("/batches/sample.zip?n=4")
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    stems = {name.rsplit("-", 1)[0] for name in names}
    assert len(stems) == 4


def test_the_batch_page_states_the_pairing_convention() -> None:
    """A convention a reviewer cannot discover is not one."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    body = client.get("/batches").text
    assert "-front" in body and "-back" in body
