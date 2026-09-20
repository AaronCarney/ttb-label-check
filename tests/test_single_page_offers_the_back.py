"""The page a reviewer lands on can send a back, and the warning on it is found.

The fault this file guards: `POST /` has accepted a second face called
`label_back` since the faces work landed, but `app/ui/templates/single.html`
offered exactly one file input, so no reviewer using the page could ever send
one. The route's own tests passed, because they post the field directly; only
the page was missing it.

The label here is a real approved one whose government warning is printed on
the back and nowhere on the front — `warning_image: "back"` in
`tests/fixtures/labels/manifest.json`. Everything is real except the step from
pixels to boxes, which is driven from the frozen readings under
`tests/recordings/reader/` (the same recordings `tests/test_vision_replay.py`
scores), so the reader, the rule pack, the route and the page are the ones that
ship.

The submissions below are built from the field names the page itself offers,
not from names written here, so the page and the route cannot drift apart
again: if the page stops offering a back, the warning check starts failing.
"""

from __future__ import annotations

import json
import re
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
    """The real app, rule pack and reader, with the OCR pass frozen."""
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
    return TestClient(app)


def _upload_field_names(html: str) -> list[str]:
    """The names of the file inputs in the page's own upload form."""
    form = re.search(r'<form action="/" method="post".*?</form>', html, re.DOTALL)
    assert form, "the landing page offered no upload form"
    return re.findall(r'<input[^>]*type="file"[^>]*name="([^"]+)"', form.group(0))


def _envelope(response) -> dict:
    assert response.status_code == 200, response.text
    embedded = re.search(
        r'<script id="envelope" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL,
    )
    assert embedded, "the page embedded no result envelope"
    return json.loads(embedded.group(1))


def _rule_outcomes(envelope: dict) -> dict[str, str]:
    return {
        entry["rule_id"]: entry["disposition"]
        for entry in envelope["audit_trail"]["per_rule_trace"]
    }


def test_the_page_offers_a_back(client: TestClient) -> None:
    names = _upload_field_names(client.get("/").text)
    assert "label" in names, names
    assert "label_back" in names, "the page offers no way to send a back label"


def test_a_warning_printed_on_the_back_is_found_when_the_page_sends_one(
    client: TestClient,
) -> None:
    """Done when a reviewer on `/` can submit a back and the warning on it is
    found. The submission uses the page's own field names."""
    names = _upload_field_names(client.get("/").text)
    assert len(names) == 2, f"the page offers {len(names)} image field(s): {names}"
    front_field, back_field = names
    files = [
        (front_field, ("front.jpg", FACE_IMAGES["front"], "image/jpeg")),
        (back_field, ("back.jpg", FACE_IMAGES["back"], "image/jpeg")),
    ]

    outcomes = _rule_outcomes(
        _envelope(client.post("/", files=files, data={"beverage_type": "distilled_spirits"}))
    )
    assert outcomes["common.warning.present"] == "pass", outcomes


def test_without_the_back_the_same_label_reports_no_warning(client: TestClient) -> None:
    """The control. The warning is genuinely on the back and nowhere else, so
    a front-only submission of this label must still report it missing."""
    files = [("label", ("front.jpg", FACE_IMAGES["front"], "image/jpeg"))]
    outcomes = _rule_outcomes(
        _envelope(client.post("/", files=files, data={"beverage_type": "distilled_spirits"}))
    )
    assert outcomes["common.warning.present"] == "fail", outcomes
