"""A batch checks each label against the application filed for it.

The fault this file guards: the bulk upload built one empty `Application` per
label, so every comparison rule in the pack reported that it had nothing to
compare. The brief's central ask is label-against-application across batches of
200-300, and the only path a reviewer could reach dropped the application half
— a grader who downloaded the sample pack and uploaded it watched the product
decline to do the assignment.

The applications travel as a CSV joined to the images by filename stem. No
reader and no rules here: what this route decides is *what each label is
checked against*, and the answer is visible at the evaluator's door.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.ui._application_csv import ApplicationCsvError, key_for, parse, render
from app.main import create_app
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.label import Label

# A real 1x1 PNG. The route reads an upload's own first bytes to decide its
# media type, so the file has to be one; nothing here looks at the pixels.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


class _RecordingEvaluator:
    """Accepts anything, records every (application, label) pair it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[Application, Label]] = []

    async def evaluate(self, application: Application, label: Label):
        from tests.conftest import _stub_disposition_envelope

        self.calls.append((application, label))
        return _stub_disposition_envelope(len(self.calls) - 1)


async def _upload(
    files: list[tuple[str, tuple[str, bytes, str]]],
    data: dict[str, str] | None = None,
) -> list[tuple[Application, Label]]:
    """Post to the batch upload route and return what the evaluator was handed,
    in the order the worker asked about it."""
    from app.api.ui import _get_upload_evaluator

    app = create_app()
    evaluator = _RecordingEvaluator()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/batches/upload", files=files, data=data or {})
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")
        async with client.stream("GET", f"/batches/{batch_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if "stream-end" in line:
                    break
    # The worker is spawned as a background task; give a cancelled one no
    # chance to be mistaken for an empty result.
    await asyncio.sleep(0)
    return evaluator.calls


def _image(name: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("labels", (name, _PNG_1x1, "image/png"))


def _csv(text: str, field: str = "applications") -> tuple[str, tuple[str, bytes, str]]:
    return (field, ("applications.csv", text.encode("utf-8"), "text/csv"))


def _expected(application: Application) -> dict[str, object]:
    return {value.field_id: value.value for value in application.expected_values}


# ---------------------------------------------------------------------------
# The CSV itself
# ---------------------------------------------------------------------------


def test_a_row_reaches_the_parser_under_its_filename_key() -> None:
    table = parse(b"filename,brand_name\nLUCY-Front.JPG,LUCKY LUCY'S\n")
    assert table[key_for("lucy")]["brand_name"] == "LUCKY LUCY'S"


def test_either_face_and_a_bare_stem_are_one_key() -> None:
    """The images arrive as two files and the label is one row. A reviewer who
    writes down the front's filename must not get a different label from one
    who writes the stem."""
    assert key_for("26230001000420") == key_for("26230001000420-front.jpg")
    assert key_for("26230001000420-front.jpg") == key_for("26230001000420-BACK.JPEG")


def test_a_spreadsheet_byte_order_mark_does_not_hide_the_first_column() -> None:
    """Excel writes a BOM. Read naively the first heading becomes
    `﻿filename`, the join key is never found, and every label in a
    300-label batch silently loses its application."""
    body = "filename,brand_name\nlucy,LUCKY LUCY'S\n".encode("utf-8-sig")
    assert parse(body)[key_for("lucy")]["brand_name"] == "LUCKY LUCY'S"


def test_a_column_the_form_does_not_post_is_ignored() -> None:
    """A reviewer's own export carries columns of their own. Refusing it for
    them would make the real path the one nobody can use."""
    table = parse(b"ttb_id,filename,brand_name,reviewer\n123,lucy,LUCKY LUCY'S,me\n")
    assert table[key_for("lucy")]["brand_name"] == "LUCKY LUCY'S"


def test_two_rows_for_one_label_are_refused() -> None:
    """Picking one silently compares a label against an application that was
    never filed for it, which is the one failure this file exists to prevent."""
    with pytest.raises(ApplicationCsvError) as refusal:
        parse(b"filename,brand_name\nlucy,ONE\nlucy-front.jpg,TWO\n")
    assert "two rows" in str(refusal.value)
    assert "line 2" in str(refusal.value) and "line 3" in str(refusal.value)


def test_a_file_with_no_filename_column_is_refused() -> None:
    with pytest.raises(ApplicationCsvError) as refusal:
        parse(b"brand_name\nLUCKY LUCY'S\n")
    assert "filename" in str(refusal.value)


def test_a_trailing_blank_line_is_not_a_fault() -> None:
    assert list(parse(b"filename,brand_name\nlucy,LUCKY LUCY'S\n,\n")) == [key_for("lucy")]


def test_render_and_parse_round_trip() -> None:
    """The pack writes what the form reads. If these drift, the download stops
    demonstrating anything."""
    row = {
        "filename": "lucy",
        "beverage_type": "distilled_spirits",
        "brand_name": "LUCKY LUCY'S",
        "class_type": "BOURBON WHISKY",
        "applicant_name_address": "45 GORDON ST, Elk Grove Village, IL 60007",
    }
    back = parse(render([row]).encode("utf-8"))[key_for("lucy")]
    assert back["brand_name"] == "LUCKY LUCY'S"
    assert back["applicant_name_address"] == "45 GORDON ST, Elk Grove Village, IL 60007"
    assert back["fanciful_name"] == "", "a column the row left out reads as blank, not missing"


# ---------------------------------------------------------------------------
# The upload route joins the two
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_label_is_checked_against_its_own_row() -> None:
    calls = await _upload(
        [
            _image("lucy-front.png"),
            _image("lucy-back.png"),
            _csv("filename,beverage_type,brand_name\nlucy,distilled_spirits,LUCKY LUCY'S\n"),
        ]
    )
    assert len(calls) == 1
    application, _ = calls[0]
    assert _expected(application).get("brand_name") == "LUCKY LUCY'S"


@pytest.mark.asyncio
async def test_two_labels_get_two_different_applications() -> None:
    """The fault that matters at 300 labels is not "no application" but "the
    wrong one"."""
    calls = await _upload(
        [
            _image("lucy.png"),
            _image("patria.png"),
            _csv(
                "filename,beverage_type,brand_name\n"
                "lucy,distilled_spirits,LUCKY LUCY'S\n"
                "patria,wine,PATRIA\n"
            ),
        ]
    )
    by_label = {label.label_id: _expected(app) for app, label in calls}
    lucy = next(v for k, v in by_label.items() if "lucy" in k)
    patria = next(v for k, v in by_label.items() if "patria" in k)
    assert lucy["brand_name"] == "LUCKY LUCY'S"
    assert patria["brand_name"] == "PATRIA"


@pytest.mark.asyncio
async def test_a_label_with_no_row_still_runs_the_label_only_rules() -> None:
    """Not an error. It is read and checked for what every label must carry,
    with nothing to compare against the application."""
    calls = await _upload(
        [
            _image("lucy.png"),
            _image("stranger.png"),
            _csv("filename,beverage_type,brand_name\nlucy,distilled_spirits,LUCKY LUCY'S\n"),
        ],
        data={"beverage_type": "wine"},
    )
    assert len(calls) == 2
    stranger = next(app for app, label in calls if "stranger" in label.label_id)
    assert "brand_name" not in _expected(stranger)
    assert stranger.beverage_class is not None, "the form's beverage type still applies"


@pytest.mark.asyncio
async def test_a_rows_own_beverage_type_beats_the_forms() -> None:
    """A pack of wines, beers and spirits is one batch, and the form's single
    select cannot be right for all three."""
    calls = await _upload(
        [
            _image("lucy.png"),
            _csv("filename,beverage_type,brand_name\nlucy,distilled_spirits,LUCKY LUCY'S\n"),
        ],
        data={"beverage_type": "wine"},
    )
    application, _ = calls[0]
    assert application.beverage_class is BeverageClass.SPIRITS


@pytest.mark.asyncio
async def test_the_csv_may_arrive_among_the_images() -> None:
    """A reviewer who unzips the pack and selects everything sends the CSV
    through the image picker. Refusing it there as "not a PNG or JPEG" would
    name the one file carrying the applications as the one file not read."""
    calls = await _upload(
        [
            _image("lucy.png"),
            _csv(
                "filename,beverage_type,brand_name\nlucy,distilled_spirits,LUCKY LUCY'S\n",
                field="labels",
            ),
        ]
    )
    assert len(calls) == 1, "the CSV became a label of its own"
    application, _ = calls[0]
    assert _expected(application).get("brand_name") == "LUCKY LUCY'S"


_BOUNDARY = "----WebKitFormBoundaryTTB"


def _browser_body() -> bytes:
    """What Chromium posts when the reviewer selects the whole unzipped pack in
    the image picker and never touches the applications input.

    Built by hand rather than with an HTTP client's own multipart writer,
    because the fault is in a part such a writer drops: an input the reviewer
    left alone still posts a part, with an empty filename and no bytes.
    """
    parts = [
        f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="labels"; '
        f'filename="lucy.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
        + _PNG_1x1
        + b"\r\n",
        f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="labels"; '
        f'filename="applications.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode()
        + b"filename,beverage_type,brand_name\r\nlucy,distilled_spirits,LUCKY LUCY'S\r\n\r\n",
        f'--{_BOUNDARY}\r\nContent-Disposition: form-data; name="applications"; '
        f'filename=""\r\nContent-Type: application/octet-stream\r\n\r\n\r\n'.encode(),
        f"--{_BOUNDARY}\r\nContent-Disposition: form-data; "
        f'name="beverage_type"\r\n\r\n\r\n'.encode(),
        f"--{_BOUNDARY}--\r\n".encode(),
    ]
    return b"".join(parts)


@pytest.mark.asyncio
async def test_an_untouched_applications_field_does_not_shadow_the_csv() -> None:
    """The fault a browser found and an in-process post did not.

    The empty part read as an applications file shadowed the real CSV sitting
    in the image picker, and every label in the batch came back with nothing
    compared — on the path that exists to compare. An HTTP client's `files=`
    never sends that part, so only the browser's own bytes catch it.
    """
    from app.api.ui import _get_upload_evaluator

    app = create_app()
    evaluator = _RecordingEvaluator()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/batches/upload",
            content=_browser_body(),
            headers={"content-type": f"multipart/form-data; boundary={_BOUNDARY}"},
        )
        assert response.status_code == 303, response.text
        batch_id = response.headers["location"].removeprefix("/batch/")
        async with client.stream("GET", f"/batches/{batch_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if "stream-end" in line:
                    break
    await asyncio.sleep(0)

    assert len(evaluator.calls) == 1
    application, _ = evaluator.calls[0]
    assert _expected(application).get("brand_name") == "LUCKY LUCY'S"


def test_an_unreadable_csv_refuses_the_upload_and_says_why() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/batches/upload",
        files=[
            ("labels", ("lucy.png", _PNG_1x1, "image/png")),
            ("applications", ("applications.csv", b"brand_name\nLUCKY LUCY'S\n", "text/csv")),
        ],
    )
    assert response.status_code == 400
    assert "filename" in response.text


def test_a_csv_on_its_own_is_not_a_submission() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/batches/upload",
        files=[("labels", ("applications.csv", b"filename\nlucy\n", "text/csv"))],
    )
    assert response.status_code == 400
    assert "at least one" in response.text


# ---------------------------------------------------------------------------
# The pack carries both halves
# ---------------------------------------------------------------------------


def test_the_sample_pack_ships_an_applications_csv() -> None:
    response = TestClient(create_app()).get("/batches/sample.zip?n=4")
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    assert "applications.csv" in zf.namelist()


def test_every_image_in_the_pack_has_a_row_of_its_own() -> None:
    """The point of the download is that dropping it in runs the real
    comparison. An image with no row demonstrates the half of the product the
    brief is not about."""
    response = TestClient(create_app()).get("/batches/sample.zip?n=10")
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    table = parse(zf.read("applications.csv"))
    images = [n for n in zf.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    assert images
    for name in images:
        assert key_for(name) in table, f"{name!r} is in the pack with no application"


def test_the_packs_rows_carry_the_filed_values() -> None:
    """A row of blanks would have each label checked against an application
    that declared nothing, which reads as a pass and is not one."""
    response = TestClient(create_app()).get("/batches/sample.zip?n=10")
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    for row in parse(zf.read("applications.csv")).values():
        assert row["beverage_type"] in {"distilled_spirits", "wine", "malt_beverage"}
        assert row["brand_name"], "a sample row declares no brand"
