# tests/test_vision_substitutability.py
import json
from collections import deque
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.schemas.label import Dimensions, Face, Label
from app.vision.base import VisionExtractor
from app.vision.cloud import CloudVisionExtractor

EXPECTED_FIELD_IDS = {
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "gov_warning",
    "name_address",
    "country_origin",
}
RECORDINGS_DIR = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/01-spirits-clean")
# A real CC0 label from the TTB Public COLA Registry, front face: distilled
# spirits, 1200x1800 JPEG. It passes the vision quality gates, so a test
# using it exercises the path a submitted label takes.
FIXTURE = Path("tests/fixtures/labels/26231001000662/front.jpg")


def _label() -> Label:
    return Label(
        label_id="L-001",
        batch_id="B-001",
        faces=(
            Face(
                image_bytes=FIXTURE.read_bytes(),
                content_type="image/jpeg",
                face_tag="front",
                dimensions=Dimensions(width_px=1200, height_px=1800, dpi=300),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_cloud_satisfies_protocol():
    settings = Settings()
    cloud = CloudVisionExtractor(
        settings=settings, ring_buffer=deque(maxlen=200), api_key="sk-test"
    )
    assert isinstance(cloud, VisionExtractor)


@pytest.mark.asyncio
async def test_cloud_produces_expected_field_id_set():
    settings = Settings()
    cloud_ring = deque(maxlen=200)
    cloud = CloudVisionExtractor(settings=settings, ring_buffer=cloud_ring, api_key="sk-test")
    # respx 0.23.1 deduplicates same-URL/method routes; collapse the planned
    # per-recording mounts into one dispatcher keyed on the request body's
    # response_format.json_schema.name.
    recordings = {p.stem: json.loads(p.read_text()) for p in RECORDINGS_DIR.glob("*.json")}
    with respx.mock(base_url="https://api.openai.com") as router:

        def _dispatch(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            payload = recordings.get(name)
            if payload is None:
                return Response(404, json={"error": f"no recording for {name!r}"})
            return Response(200, json=payload)

        router.post("/v1/chat/completions").mock(side_effect=_dispatch)
        cloud_obs = await cloud.extract(_label())

    cloud_ids = {o.field_id for o in cloud_obs}
    # The full canonical field_id set must round-trip through the seam.
    assert cloud_ids == EXPECTED_FIELD_IDS


# ---------------------------------------------------------------------------
# The seam itself: the same label must mean the same thing whichever reader
# read it. Both of the tests above drive only the cloud reader, so neither of
# them can see a disagreement between the two.
# ---------------------------------------------------------------------------

READER_RECORDINGS = Path("tests/recordings/reader")

# Keys the cloud reader adds that the local reader has no counterpart for, and
# why each is allowed to be one-sided. `OBSERVED_VALUE_AUDIT_KEYS` in
# `app/vision/cloud.py` is what strips them from the user-facing projection.
CLOUD_ONLY_KEYS = frozenset(
    {
        # What the model claimed about the heading's weight, kept beside the
        # measurement that overrode it. The local reader has nothing to keep: it
        # never asks a model.
        "heading_bold_llm",
    }
)


def _reader_payloads(relative: str) -> dict[str, dict]:
    """One frozen local reading, parsed. No model, no image, no network."""
    from app.vision.local import parse_reading, thaw_reading

    path = (READER_RECORDINGS / relative).with_suffix(".json")
    return parse_reading(thaw_reading(json.loads(path.read_text())))


def _cloud_payloads(
    per_field: dict[str, dict], *, measurement=None
) -> tuple[dict[str, dict], dict[str, object], list[dict]]:
    """The cloud reader's observations, its evidence and every request it sent.

    The heading measurement is supplied rather than taken off the fixture, so a
    test can say which branch of the boldness override it is asking about.
    """
    import asyncio
    from unittest import mock

    from app.vision import cloud as cloud_module

    settings = Settings()
    extractor = CloudVisionExtractor(
        settings=settings, ring_buffer=deque(maxlen=200), api_key="sk-test"
    )
    sent: list[dict] = []

    async def _run() -> list:
        with respx.mock(base_url="https://api.openai.com") as router:

            def _dispatch(request):
                body = json.loads(request.content)
                sent.append(body)
                name = body["response_format"]["json_schema"]["name"]
                return Response(
                    200,
                    json={
                        "id": "x",
                        "object": "chat.completion",
                        "model": "gpt-4o",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": json.dumps(per_field[name]),
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    },
                )

            router.post("/v1/chat/completions").mock(side_effect=_dispatch)
            if measurement is None:
                return await extractor.extract(_label())
            with mock.patch.object(cloud_module, "measure_heading_bold", return_value=measurement):
                return await extractor.extract(_label())

    observations = asyncio.run(_run())
    payloads = {o.field_id: o.observed_value for o in observations}
    evidence = {o.field_id: o.evidence[0] for o in observations}
    return payloads, evidence, sent


def _full_response(**overrides) -> dict[str, dict]:
    """A complete set of per-field answers, one per call the reader makes."""
    answers = {
        "layout": {"fields": []},
        "brand_name": {"brand_name": "ACME BOURBON", "confidence": 0.9},
        "class_type": {"class_type": "BOURBON", "confidence": 0.9},
        "abv": {
            "abv_pct": 40.0,
            "unit": "%",
            "alc_text": "40% ALC/VOL",
            "confidence": 0.9,
        },
        "net_contents": {
            "net_contents_value": 750.0,
            "unit": "ML",
            "confidence": 0.9,
        },
        "gov_warning": {
            "text": "GOVERNMENT WARNING: …",
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
            "heading_bold": True,
            "type_size_pt": 8.0,
            "confidence": 0.9,
        },
        "name_address": {
            "name": "ACME",
            "city": "FRANKFORT",
            "state": "KY",
            "confidence": 0.9,
        },
        "country_origin": {"country": "USA", "confidence": 0.9},
    }
    answers.update(overrides)
    return answers


def test_the_two_readers_describe_a_field_with_the_same_keys() -> None:
    """A rule reads one payload and does not know which reader filled it.

    So a key one reader emits and the other does not is a rule that finds its
    evidence on one path and nothing on the other. `alc_text` was exactly that:
    the local reader returns the alcohol statement as the label prints it — the
    key the rule packs name in `evidence_required` — and the cloud schema had
    no room for it at all.
    """
    from app.vision.heading_measure import HeadingMeasurement

    measured = HeadingMeasurement(True, 3.0, 12.0, 0.25, confident=True)
    cloud, _evidence, _sent = _cloud_payloads(_full_response(), measurement=measured)
    # A local reading whose heading was measured, so the same branch of the
    # boldness override is being compared on both sides.
    local = _reader_payloads("26230001000420/back.jpg")

    for field_id in EXPECTED_FIELD_IDS:
        assert set(cloud[field_id]) - CLOUD_ONLY_KEYS == set(local[field_id]), field_id


def test_a_number_neither_reader_could_read_is_absent_from_both() -> None:
    """The defect this seam was opened for.

    The cloud schemas marked `abv_pct` and `net_contents_value` as plain
    numbers and required them, so a model that could not read the figure had to
    return one anyway. A number the model invented is compared against the
    application and rejects the label; the local reader's `None` sends the same
    image to a reviewer. Same unreadable label, opposite verdict.
    """
    from app.vision.local import _Box, _parse

    # The local half: a label whose boxes carry neither figure.
    blank = _parse(
        boxes=[_Box(x0=0.0, y0=0.0, x1=300.0, y1=40.0, text="ACME BOURBON", score=0.9)],
        warning_boxes=[],
        rotation=0,
    )
    assert blank["abv"][0]["abv_pct"] is None
    assert blank["net_contents"][0]["net_contents_value"] is None

    # The cloud half: the schema has to permit the same answer, and the key
    # stays required — Structured Outputs expresses "optional" as a union with
    # null, not as an absent key.
    from app.vision.cloud import _SCHEMAS

    for field_id, key in (("abv", "abv_pct"), ("net_contents", "net_contents_value")):
        schema = _SCHEMAS[field_id]
        assert schema["properties"][key]["type"] == ["number", "null"], field_id
        assert key in schema["required"], field_id

    # And it survives the journey: a null comes back as a null, not as a zero.
    unread = _full_response(
        abv={"abv_pct": None, "unit": "", "alc_text": "", "confidence": 0.2},
        net_contents={"net_contents_value": None, "unit": "", "confidence": 0.2},
    )
    cloud, _evidence, _sent = _cloud_payloads(unread)
    assert cloud["abv"]["abv_pct"] is None
    assert cloud["net_contents"]["net_contents_value"] is None


def test_the_cloud_reader_pins_its_sampling_on_every_call() -> None:
    """A sampled boolean can reject a label, and the reader used to sample at
    the API's default of 1.0 — so the same image read twice could give a
    reviewer two different answers with nothing to show for the difference.

    Checked on the bodies the reader actually sends, all eight of them, because
    the body is the only place the setting exists.
    """
    from app.vision.cloud import _SAMPLING_SEED

    _payloads, _evidence, sent = _cloud_payloads(_full_response())
    assert len(sent) == 8, len(sent)
    for body in sent:
        assert body["temperature"] == 0, body["response_format"]["json_schema"]["name"]
        assert body["seed"] == _SAMPLING_SEED
        # `top_p` is the other half of the same dial and the provider asks that
        # only one of the two be moved.
        assert "top_p" not in body


def test_a_cloud_reading_says_the_model_is_where_it_came_from() -> None:
    """Every reading was recorded as `LAYOUT`, which names where the *box* came
    from and says nothing about the *value* — and the value is what a rule
    compares. The local reader says `OCR` on the same seam."""
    from app.schemas.extracted import EvidenceSource

    _payloads, evidence, _sent = _cloud_payloads(_full_response())
    for field_id in EXPECTED_FIELD_IDS:
        assert evidence[field_id].source is EvidenceSource.CLASSIFIER, field_id


def test_a_boldness_nobody_measured_is_absent_from_both_readers() -> None:
    """The local reader stopped writing `heading_bold` when the stroke-width
    measurement was not confident, because writing it stated a measurement
    nobody took. The cloud reader kept the model's own guess there, so the same
    heading was a claim from one reader and an absence from the other.

    `heading_style_check.py` asks `heading_bold_measured_confident` before it
    looks at the weight, so no verdict moves — what moves is what the envelope
    says the product knows.
    """
    from app.vision.heading_measure import HeadingMeasurement

    unmeasured = HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)
    cloud, _evidence, _sent = _cloud_payloads(_full_response(), measurement=unmeasured)
    warning = cloud["gov_warning"]
    assert warning["heading_bold_measured_confident"] is False
    assert "heading_bold" not in warning
    # The model's answer is not lost, it is filed where the audit trail wants it.
    assert warning["heading_bold_llm"] is True

    # The local reader, on the recording that actually produces the case: a
    # handwritten keg collar whose heading could not be measured.
    local = _reader_payloads("26240001000454/front.jpg")["gov_warning"]
    assert local["heading_bold_measured_confident"] is False
    assert "heading_bold" not in local
