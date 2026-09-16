# tests/test_vision_substitutability.py
import json
from collections import deque
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.schemas.label import Dimensions, Label
from app.vision.base import VisionExtractor
from app.vision.cloud import CloudVisionExtractor

EXPECTED_FIELD_IDS = {
    "brand_name", "class_type", "abv", "net_contents",
    "gov_warning", "name_address", "country_origin",
}
RECORDINGS_DIR = Path("tests/recordings/openai/gpt-4o-2024-08-06/v1/01-spirits-clean")
# A real CC0 label from the TTB Public COLA Registry, front face: distilled
# spirits, 1200x1800 JPEG. It passes the vision quality gates, so a test
# using it exercises the path a submitted label takes.
FIXTURE = Path("tests/fixtures/labels/26231001000662/front.jpg")


def _label() -> Label:
    return Label(
        label_id="L-001", batch_id="B-001",
        image_bytes=FIXTURE.read_bytes(), content_type="image/jpeg",
        face_tag="front",
        dimensions=Dimensions(width_px=1200, height_px=1800, dpi=300),
    )


@pytest.mark.asyncio
async def test_cloud_satisfies_protocol():
    settings = Settings()
    cloud = CloudVisionExtractor(settings=settings, ring_buffer=deque(maxlen=200), api_key="sk-test")
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
