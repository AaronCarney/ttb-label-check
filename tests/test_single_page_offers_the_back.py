"""The page a reviewer lands on can send a back, and the warning on it is found.

The fault this file guards: the route has accepted a second face since the
faces work landed, but the page offered exactly one file input, so no reviewer
using the page could ever send one. The route's own tests passed, because they
post the field directly; only the page was missing it.

The page has since become the only way in — one form for one label or three
hundred (`docs/decisions.md#0045`) — so the second face now arrives one of two
ways, and both are checked below: two files named `<stem>-front` and
`<stem>-back`, or any two files with *These images are all faces of one label*
ticked. The fault would return in the same shape if the form stopped offering
either.

The label here is a real approved one whose government warning is printed on
the back and nowhere on the front — `warning_image: "back"` in
`tests/fixtures/labels/manifest.json`. Everything is real except the step from
pixels to boxes, which is driven from the frozen readings under
`tests/recordings/reader/` (the same recordings `tests/test_vision_replay.py`
scores), so the reader, the rule pack, the route and the page are the ones that
ship.

The submissions below are built from the field names the page itself offers,
not from names written here, so the page and the route cannot drift apart
again: if the page stops offering a way to send a back, the warning check
starts failing.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.ui import _get_upload_evaluator
from app.config import Settings
from app.main import create_app
from app.rules import build_rule_engine
from app.services.evaluator import Evaluator
from app.vision.local import LocalVisionExtractor, _parse, thaw_reading

TTB_ID = "26229001000034"
LABELS = Path("tests/fixtures/labels") / TTB_ID
RECORDINGS = Path("tests/recordings/reader") / TTB_ID
FACE_IMAGES = {tag: (LABELS / f"{tag}.jpg").read_bytes() for tag in ("front", "back")}


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """The real app, rule pack and reader, with the OCR pass frozen.

    Entered as a context manager: the check runs as a background task on the
    app's own loop, and a bare TestClient tears that loop down between requests.
    """
    by_bytes = {image: tag for tag, image in FACE_IMAGES.items()}

    def _frozen(image_bytes: bytes):
        reading = thaw_reading(
            json.loads((RECORDINGS / f"{by_bytes[image_bytes]}.json").read_text())
        )
        payloads = _parse(
            boxes=reading.boxes,
            warning_boxes=reading.warning_boxes,
            rotation=reading.rotation,
            heading_measurement=reading.heading_measurement,
        )
        return payloads, {
            "reader": "local",
            "engine": "rapidocr",
            "rotation_deg": reading.rotation,
            "boxes_found": len(reading.boxes),
        }

    monkeypatch.setattr(LocalVisionExtractor, "_read_serialised", staticmethod(_frozen))

    async def _loaded(self):
        return None

    monkeypatch.setattr(LocalVisionExtractor, "ensure_loaded", _loaded)

    settings = Settings()
    evaluator = Evaluator(
        vision=LocalVisionExtractor(settings=settings, ring_buffer=deque(maxlen=50)),
        rules=build_rule_engine(settings),
        settings=settings,
    )
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    with TestClient(app) as entered:
        yield entered


def _form(html: str) -> str:
    form = re.search(r'<form action="/" method="post".*?</form>', html, re.DOTALL)
    assert form, "the landing page offered no upload form"
    return form.group(0)


def _image_field(html: str) -> str:
    """The name of the file input the page offers for label photographs.

    The form has a second file input for the applications CSV, so the one
    wanted here is the one that says it takes images.
    """
    form = _form(html)
    inputs = re.findall(r"<input[^>]*type=\"file\"[^>]*/>", form)
    named = [
        re.search(r'name="([^"]+)"', tag).group(1)
        for tag in inputs
        if "image/png" in tag or "image/jpeg" in tag
    ]
    assert len(named) == 1, f"the page offers {len(named)} label-image field(s): {named}"
    return named[0]


def _one_label_field(html: str) -> str:
    """The name of the checkbox that says every image is one label's faces."""
    form = _form(html)
    match = re.search(
        r'<input[^>]*type="checkbox"[^>]*name="([^"]+)"[^>]*/>\s*'
        r"<label[^>]*>These images are all faces of one label</label>",
        form,
    )
    assert match, "the page offers no way to say two photographs are one label"
    return match.group(1)


def _only_result(client: TestClient, response) -> dict:
    """The one label's finished result, read off the batch it was checked in."""
    assert response.status_code == 303, response.text
    batch_id = response.headers["location"].removeprefix("/batch/")
    deadline = time.monotonic() + 20.0
    items: list[dict] = []
    while time.monotonic() < deadline:
        items = client.get(f"/batches/{batch_id}").json()["items"]
        if items and all(item["state"] in ("ready", "failed") for item in items):
            break
        time.sleep(0.02)
    assert len(items) == 1, items
    assert items[0]["result"] is not None, items[0]
    return items[0]["result"]


def _rule_outcomes(envelope: dict) -> dict[str, str]:
    return {
        entry["rule_id"]: entry["disposition"]
        for entry in envelope["audit_trail"]["per_rule_trace"]
    }


def test_the_page_offers_a_back(client: TestClient) -> None:
    """Two ways to send one, and the page has to say so: a picker that takes
    more than one file, and the checkbox for photographs not named for pairing.
    """
    page = client.get("/").text
    form = _form(page)
    picker = next(
        tag
        for tag in re.findall(r"<input[^>]*type=\"file\"[^>]*/>", form)
        if f'name="{_image_field(page)}"' in tag
    )
    assert "multiple" in picker, (
        "the page's file picker takes one file, so a back cannot be sent with a front"
    )
    assert _one_label_field(page)
    assert "-back" in page, "the page does not state the pairing convention"


def test_a_warning_printed_on_the_back_is_found_when_the_page_sends_one(
    client: TestClient,
) -> None:
    """Done when a reviewer on `/` can submit a back and the warning on it is
    found. The submission uses the page's own field name and its own stated
    naming convention."""
    field = _image_field(client.get("/").text)
    files = [
        (field, (f"{TTB_ID}-front.jpg", FACE_IMAGES["front"], "image/jpeg")),
        (field, (f"{TTB_ID}-back.jpg", FACE_IMAGES["back"], "image/jpeg")),
    ]

    outcomes = _rule_outcomes(
        _only_result(
            client,
            client.post(
                "/",
                files=files,
                data={"beverage_type": "distilled_spirits"},
                follow_redirects=False,
            ),
        )
    )
    assert outcomes["common.warning.present"] == "pass", outcomes


def test_two_photographs_not_named_for_pairing_are_one_label_when_the_box_is_ticked(
    client: TestClient,
) -> None:
    """The reviewer photographed both faces on a phone. Nothing in those two
    filenames pairs them, and renaming files is not a thing to ask of someone
    checking one label — so the checkbox pairs them instead, and the warning on
    the back is found exactly as it is for a named pair."""
    page = client.get("/").text
    field = _image_field(page)
    files = [
        (field, ("IMG_4417.jpg", FACE_IMAGES["front"], "image/jpeg")),
        (field, ("IMG_4418.jpg", FACE_IMAGES["back"], "image/jpeg")),
    ]

    outcomes = _rule_outcomes(
        _only_result(
            client,
            client.post(
                "/",
                files=files,
                data={"beverage_type": "distilled_spirits", _one_label_field(page): "1"},
                follow_redirects=False,
            ),
        )
    )
    assert outcomes["common.warning.present"] == "pass", outcomes


def test_without_the_back_the_same_label_reports_no_warning(client: TestClient) -> None:
    """The control. The warning is genuinely on the back and nowhere else, so
    a front-only submission of this label must still report it missing."""
    field = _image_field(client.get("/").text)
    files = [(field, ("front.jpg", FACE_IMAGES["front"], "image/jpeg"))]
    outcomes = _rule_outcomes(
        _only_result(
            client,
            client.post(
                "/",
                files=files,
                data={"beverage_type": "distilled_spirits"},
                follow_redirects=False,
            ),
        )
    )
    assert outcomes["common.warning.present"] == "fail", outcomes
