# tests/test_vision_ring_buffer_records.py
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
# A real CC0 label from the TTB Public COLA Registry, front face: distilled
# spirits, 1200x1800 JPEG. It passes the vision quality gates, so a test
# using it exercises the path a submitted label takes.
FIXTURE = Path("tests/fixtures/labels/26231001000662/front.jpg")


@pytest.mark.asyncio
async def test_cloud_writes_9_call_records():
    settings = Settings()
    ring = deque(maxlen=200)
    extractor = CloudVisionExtractor(settings=settings, ring_buffer=ring, api_key="sk-test")
    label = Label(
        label_id="L-001", batch_id="B-001",
        image_bytes=FIXTURE.read_bytes(),
        content_type="image/jpeg", face_tag="front",
        dimensions=Dimensions(width_px=1200, height_px=1800, dpi=300),
    )
    # respx 0.23.1 dedupes same-URL/method routes (only the last mount survives),
    # so the closure-per-recording pattern collapses. Equivalent dispatcher keyed
    # on the request body's response_format.json_schema.name, the same pattern
    # test_vision_cloud_extraction.py uses.
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
        await extractor.extract(label)
    assert len(ring) == 8
    stages = [r.stage for r in ring]
    # 1 layout call + 7 per-field calls (heading_typography folded into
    # gov_warning post-consolidation); all under vision.gpt4o_tiebreak per
    # cloud-mode policy.
    assert all(s == "vision.gpt4o_tiebreak" for s in stages)
    assert all(r.provider == "openai" for r in ring)
    assert all(r.model == "gpt-4o-2024-08-06" for r in ring)


def test_ring_buffer_maxlen_honored():
    ring = deque(maxlen=200)
    for i in range(250):
        ring.append(i)
    assert len(ring) == 200
    assert ring[0] == 50  # oldest 50 evicted (FIFO)
