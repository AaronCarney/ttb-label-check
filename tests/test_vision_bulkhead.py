# tests/test_vision_bulkhead.py
import asyncio
from collections import deque

import pytest

from app.config import Settings
from app.schemas.label import Dimensions, Label
from app.vision import cloud as cloud_mod
from app.vision.cloud import CloudVisionExtractor
from app.vision.quality import QualityReport


@pytest.mark.asyncio
async def test_semaphore_caps_at_4(monkeypatch):
    """Five concurrent extracts: at most 4 in-flight at any point."""
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_call(*a, **kw):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        # Return shape matching what cloud.py expects.
        return {"brand_name": "X"}  # minimal stub

    # Bypass the PIL-based quality gate; test only exercises the bulkhead.
    monkeypatch.setattr(
        cloud_mod.quality,
        "assess",
        lambda label: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )

    settings = Settings()
    extractor = CloudVisionExtractor(
        settings=settings, ring_buffer=deque(maxlen=200), api_key="sk-test",
    )
    monkeypatch.setattr(extractor, "_call_per_field", fake_call)

    label = Label(
        label_id="L-001", batch_id="B-001",
        image_bytes=b"\x89PNG\r\n\x1a\n", content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )
    # 5 concurrent extract() calls — but each spawns 9 sub-calls under the same semaphore.
    await asyncio.gather(*(extractor.extract(label) for _ in range(5)))
    assert max_in_flight <= 4
