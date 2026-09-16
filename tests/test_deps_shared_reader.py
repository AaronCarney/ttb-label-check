"""Regression: the process shares one reader, and reads do not overlap.

A new reader per request made every label pay the OCR model load — about a
second off disk — made the ``/healthz`` readiness probe warm a reader it then
discarded, and threw away the reader's call ring buffer with the request that
built it. ``get_vision_extractor`` holds one reader for the process; these tests
anchor that, and anchor the serialisation that sharing an engine requires.

No models are loaded here: constructing ``LocalVisionExtractor`` is cheap, and
the blocking read is replaced with a stub.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app.config import Settings
from app.deps import build_evaluator, get_vision_extractor, reset_vision_extractor
from app.logging.ring_buffer import new_call_ring_buffer
from app.vision.cloud import CloudVisionExtractor
from app.vision.local import LocalVisionExtractor


@pytest.fixture(autouse=True)
def _no_reader_left_behind():
    reset_vision_extractor()
    yield
    reset_vision_extractor()


def test_build_evaluator_shares_one_reader_across_calls():
    settings = Settings()
    first = build_evaluator(settings)
    second = build_evaluator(settings)
    assert first._vision is second._vision, (
        "the reader must be a process singleton; a new one per request makes "
        "every label reload the OCR models"
    )


def test_the_shared_reader_keeps_its_call_ring_buffer():
    settings = Settings()
    first = build_evaluator(settings)
    first._vision._ring.append("a read happened")
    second = build_evaluator(settings)
    assert list(second._vision._ring) == ["a read happened"], (
        "records of past reads must survive the request that made them"
    )


def test_reset_drops_the_shared_reader():
    settings = Settings()
    before = get_vision_extractor(settings)
    reset_vision_extractor()
    assert get_vision_extractor(settings) is not before


def test_a_change_of_mode_gets_the_reader_it_asked_for(monkeypatch):
    local = get_vision_extractor(Settings())
    assert isinstance(local, LocalVisionExtractor)

    monkeypatch.setenv("VISION_MODE", "cloud")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cloud = get_vision_extractor(Settings())

    assert isinstance(cloud, CloudVisionExtractor), (
        "the cached reader must not outlive the mode it was built for"
    )


def test_the_cloud_reader_is_not_shared(monkeypatch):
    """Only the reader with models to load is shared.

    The cloud reader loads nothing, and it holds an ``asyncio.Semaphore``, which
    binds to the first event loop that awaits it and rejects the next. Sharing
    one across a process would hand a second loop a primitive it cannot use.
    """
    monkeypatch.setenv("VISION_MODE", "cloud")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    first = get_vision_extractor(Settings())
    second = get_vision_extractor(Settings())

    assert isinstance(first, CloudVisionExtractor)
    assert first is not second, "the cloud reader must be built per request"


def test_reads_on_the_shared_reader_do_not_overlap():
    """One engine serves every request, so two reads must queue, not overlap."""
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=new_call_ring_buffer())
    live = 0
    overlapped = False

    def _slow_read(image_bytes: bytes):
        nonlocal live, overlapped
        live += 1
        overlapped = overlapped or live > 1
        time.sleep(0.05)
        live -= 1
        return ({}, {})

    reader._read = _slow_read

    async def _two_at_once():
        await asyncio.gather(
            asyncio.to_thread(reader._read_serialised, b""),
            asyncio.to_thread(reader._read_serialised, b""),
        )

    asyncio.run(_two_at_once())

    assert not overlapped, "two reads ran through one shared engine at the same time"


def test_the_load_guard_survives_a_second_event_loop():
    """The shared reader outlives the loop it first loaded on.

    A request-scoped reader never saw a second event loop. A process-wide one
    does, and an ``asyncio.Lock`` would refuse the second loop, so the guards
    are threading locks.
    """
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=new_call_ring_buffer())
    reader._load = lambda: object()

    asyncio.run(_load_once(reader))
    engine = reader._engine
    asyncio.run(_load_once(reader))

    assert reader._engine is engine, "the second loop must reuse the loaded engine"


async def _load_once(reader: LocalVisionExtractor) -> None:
    await reader.ensure_loaded()


def test_the_load_runs_once_under_concurrent_callers():
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=new_call_ring_buffer())
    loads = 0
    lock = threading.Lock()

    def _count_load():
        nonlocal loads
        with lock:
            loads += 1
        time.sleep(0.02)
        return object()

    reader._load = _count_load

    async def _four_at_once():
        await asyncio.gather(*(reader.ensure_loaded() for _ in range(4)))

    asyncio.run(_four_at_once())

    assert loads == 1, "four callers must wait on one load, not build four engines"
