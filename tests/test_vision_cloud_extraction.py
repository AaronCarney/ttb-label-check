import json
from collections import deque
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.schemas.label import Dimensions, Label
from app.vision.cloud import CloudVisionExtractor

RECORDINGS_DIR = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/01-spirits-clean")
FIXTURE = Path("fixtures/01-spirits-clean/label.png")
EXPECTED_FIELD_IDS = {
    "brand_name", "class_type", "abv", "net_contents",
    "gov_warning", "name_address", "country_origin",
}


@pytest.mark.asyncio
async def test_cloud_extracts_fr_001_to_008(monkeypatch):
    settings = Settings()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    ring = deque(maxlen=200)
    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring, api_key="sk-test")
    label = Label(
        label_id="L-001",
        batch_id="B-001",
        image_bytes=FIXTURE.read_bytes(),
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )
    # respx 0.23.1 deduplicates same-URL/method routes (only the last mount
    # survives), so the planned per-recording mount-with-fall-through pattern
    # collapses. Equivalent: one dispatcher handler keyed on the request body's
    # `response_format.json_schema.name` (still discriminates by recording).
    recordings = {p.stem: json.loads(p.read_text()) for p in RECORDINGS_DIR.glob("*.json")}

    with respx.mock(base_url="https://api.openai.com") as mock_router:
        def _dispatch(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            payload = recordings.get(name)
            if payload is None:
                return Response(404, json={"error": f"no recording for {name!r}"})
            return Response(200, json=payload)

        mock_router.post("/v1/chat/completions").mock(side_effect=_dispatch)

        observations = await extractor.extract(label)
    field_ids = {obs.field_id for obs in observations}
    assert field_ids == EXPECTED_FIELD_IDS
    assert len(ring) == 8  # 1 layout + 7 per-field calls (heading_typography folded into gov_warning)


@pytest.mark.asyncio
async def test_cloud_threads_self_reported_confidence(monkeypatch):
    """A live response carrying `confidence` lands on Evidence.confidence
    rather than the 0.7 fallback."""
    settings = Settings()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    ring = deque(maxlen=200)
    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring, api_key="sk-test")
    label = Label(
        label_id="L-conf",
        batch_id="B-conf",
        image_bytes=FIXTURE.read_bytes(),
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )
    per_field = {
        "brand_name": {"brand_name": "ACME BOURBON", "confidence": 0.92},
        "class_type": {"class_type": "BOURBON", "confidence": 0.88},
        "abv": {"abv_pct": 40.0, "unit": "%", "confidence": 0.81},
        "net_contents": {"net_contents_value": 750, "unit": "ML", "confidence": 0.97},
        "gov_warning": {
            "text": "GOVERNMENT WARNING…",
            "heading_text": "GOVERNMENT WARNING",
            "heading_all_caps": True,
            "heading_bold": True,
            "type_size_pt": 8.0,
            "confidence": 0.55,
        },
        "name_address": {
            "name": "ACME", "city": "FRANKFORT", "state": "KY", "confidence": 0.73,
        },
        "country_origin": {"country": "USA", "confidence": 0.66},
        "layout": {"fields": []},
    }
    with respx.mock(base_url="https://api.openai.com") as mock_router:
        def _dispatch(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            payload = per_field[name]
            return Response(200, json={
                "id": "x", "object": "chat.completion", "model": "gpt-4o",
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                       "content": json.dumps(payload)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            })
        mock_router.post("/v1/chat/completions").mock(side_effect=_dispatch)
        observations = await extractor.extract(label)
    by_field = {obs.field_id: obs for obs in observations}
    assert by_field["brand_name"].evidence[0].confidence == pytest.approx(0.92)
    assert by_field["gov_warning"].evidence[0].confidence == pytest.approx(0.55)
    assert by_field["country_origin"].evidence[0].confidence == pytest.approx(0.66)


@pytest.mark.asyncio
async def test_cloud_falls_back_when_confidence_absent(monkeypatch):
    """Old recordings (and any model omission) preserve the legacy 0.7 floor
    instead of crashing or serving NaN downstream."""
    settings = Settings()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    ring = deque(maxlen=200)
    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring, api_key="sk-test")
    label = Label(
        label_id="L-old",
        batch_id="B-old",
        image_bytes=FIXTURE.read_bytes(),
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )
    # Old-shape responses missing the confidence key; replays the on-disk recordings.
    recordings = {p.stem: json.loads(p.read_text()) for p in RECORDINGS_DIR.glob("*.json")}
    with respx.mock(base_url="https://api.openai.com") as mock_router:
        def _dispatch(request):
            body = json.loads(request.content)
            name = body.get("response_format", {}).get("json_schema", {}).get("name")
            return Response(200, json=recordings[name])
        mock_router.post("/v1/chat/completions").mock(side_effect=_dispatch)
        observations = await extractor.extract(label)
    for obs in observations:
        assert obs.evidence[0].confidence == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_cloud_short_circuits_on_quality_failure(monkeypatch):
    settings = Settings()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    ring = deque(maxlen=200)
    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring, api_key="sk-test")
    from PIL import Image
    from io import BytesIO
    img = Image.new("L", (32, 32), color=128)
    buf = BytesIO()
    img.save(buf, "PNG")
    bad_bytes = buf.getvalue()

    label = Label(
        label_id="L-002",
        batch_id="B-001",
        image_bytes=bad_bytes,
        content_type="image/png",
        face_tag="front",
        dimensions=None,
    )
    # assert_all_called=False because the whole point is that the route is
    # registered but never hit (short-circuit fires before any HTTP call).
    with respx.mock(base_url="https://api.openai.com", assert_all_called=False) as mock_router:
        route = mock_router.post("/v1/chat/completions").mock(return_value=Response(200, json={}))
        observations = await extractor.extract(label)
        assert route.call_count == 0  # NO openai calls when quality fails
    assert len(observations) == 1
    assert observations[0].field_id == "quality"
    assert observations[0].upstream_meta["disposition"] == "needs_better_photo"
