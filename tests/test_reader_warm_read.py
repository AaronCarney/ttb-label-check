"""The warm read runs all three OCR models, not just the first one.

``LocalVisionExtractor.warm`` exists to move a cost off the first label:
onnxruntime optimizes each graph and allocates its arenas on the first
inference, so a reader whose models are merely loaded still makes whoever
submits first wait. Warming with a read pays it early instead.

That only works if the image the warm read runs on carries text the detector
finds. The engine is a pipeline — detect, then classify orientation, then
recognize — and a frame with no detected box stops at the first stage. The
recognition model is the largest of the three, so a warm read that detects
nothing leaves most of the cost exactly where it was, while the endpoint
reports that it warmed. Nothing about the generated image makes that visible;
these tests are what holds it.

The detection test drives the real engine, which costs about a second to load.
That is the point of it: a stub cannot say whether a real detector finds this
image's text.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.logging.ring_buffer import new_call_ring_buffer
from app.vision.local import LocalVisionExtractor, _warm_image_bytes


def _reader() -> LocalVisionExtractor:
    return LocalVisionExtractor(settings=Settings(), ring_buffer=new_call_ring_buffer())


def test_the_detector_finds_text_on_the_warm_image():
    """The claim ``warm``'s docstring makes, held against the real engine.

    Measured here when written: one box, reading "WARM 750 ML 40% ALC/VOL" at
    0.99 confidence. The assertions stay looser than that — what the text says
    does not matter and a model update may re-cut the box — but a box with
    characters in it is the whole claim, because the characters can only have
    come from the recognition model.
    """
    reader = _reader()
    reader._engine = reader._load()

    reading = reader.look(_warm_image_bytes())

    assert reading.boxes, (
        "the detector found nothing on the warm image, so the warm read stops "
        "before the recognition model and leaves most of the first label's "
        "cost unpaid"
    )
    assert any(box.text.strip() for box in reading.boxes), (
        "a box was detected but no characters came back, so the recognition "
        "model — the largest of the three — did not run"
    )


@pytest.mark.asyncio
async def test_warm_loads_before_it_reads():
    """A reader that has never loaded still warms: ``warm`` loads first."""
    reader = _reader()
    loads = 0
    reads: list[bytes] = []

    def _fake_load():
        nonlocal loads
        loads += 1
        return object()

    reader._load = _fake_load
    reader._read_serialised = lambda image_bytes: reads.append(image_bytes) or ({}, {})

    await reader.warm()

    assert loads == 1, "warm has to build the models it is about to run"
    assert reads == [_warm_image_bytes()], "warm has to run one read, not none"


@pytest.mark.asyncio
async def test_a_failed_warm_read_does_not_take_the_process_down(caplog):
    """Warming is a cost saving, not a readiness check.

    ``ensure_loaded`` answers whether the process can read labels at all, and
    ``warm`` awaits it, so a reader that cannot load still raises. What must
    not raise is the read itself: a warm that did not happen costs the first
    label what it always cost, while a warm that propagates costs the process.
    """
    reader = _reader()
    reader._load = lambda: object()

    def _boom(image_bytes: bytes):
        raise RuntimeError("engine fell over mid-warm")

    reader._read_serialised = _boom

    with caplog.at_level("WARNING", logger="app.vision.local"):
        await reader.warm()

    assert any(
        record.msg == "reader_warm_read_failed" for record in caplog.records
    ), "a warm read that failed silently is a cost nobody knows is still there"


@pytest.mark.asyncio
async def test_warm_still_raises_when_the_models_will_not_load():
    """Readiness is not swallowed: /healthz has to answer 503 on a bad load."""
    reader = _reader()

    def _cannot_load():
        raise RuntimeError("no OCR models on disk")

    reader._load = _cannot_load

    with pytest.raises(RuntimeError, match="no OCR models on disk"):
        await reader.warm()
