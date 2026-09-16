"""The local reader is held to a thread cap, and the cap is proved to have taken
effect rather than proved to have been passed.

Why this file exists. ``rapidocr`` applies a thread setting only when
``1 <= n <= os.cpu_count()`` (``rapidocr/inference_engine/onnxruntime/main.py``).
Outside that window it drops the setting with no error and no log line, and the
engine then runs on every core the machine has. So "the argument was passed" is
not evidence: what counts is what the built session reports back.

Most of this file loads no model. The last test does — it is the only way to
read a live ``InferenceSession``'s options — so it is skipped unless
``TTB_OCR_MODELS`` is set, the shape ``tests/test_deploy_healthz.py`` already
uses. A default ``pytest`` run, including one from a clean clone, loads nothing.
"""
from __future__ import annotations

import os
from collections import deque

import pytest

from app.config import Settings
from app.vision.local import LocalVisionExtractor

_INTRA = "EngineConfig.onnxruntime.intra_op_num_threads"
_INTER = "EngineConfig.onnxruntime.inter_op_num_threads"


def _reader(threads: int) -> LocalVisionExtractor:
    return LocalVisionExtractor(settings=Settings(ocr_num_threads=threads), ring_buffer=deque())


class _StubRapidOCR:
    """Stands in for the engine so the cap can be read without loading models."""

    last_params: dict | None = None

    def __init__(self, params: dict | None = None) -> None:
        type(self).last_params = params


def test_default_thread_cap_is_the_deploy_targets_core_count() -> None:
    """Four, because the Cloud Run service is 4 vCPU (decision 0025).

    The local run then behaves like the deployed product rather than like a
    16-core developer machine.
    """
    assert Settings().ocr_num_threads == 4


def test_cap_is_clamped_into_the_window_onnxruntime_accepts() -> None:
    """A number above the machine's core count would be dropped in silence, and
    dropping it means every core. It is clamped to the core count instead."""
    available = os.cpu_count() or 1
    assert _reader(available + 16)._thread_cap() == available
    assert _reader(2)._thread_cap() == min(2, available)


def test_a_thread_count_below_one_is_refused_at_configuration_time() -> None:
    """Zero is the other silently-ignored value, so it never reaches the engine."""
    with pytest.raises(Exception):
        Settings(ocr_num_threads=0)


def test_load_passes_the_cap_on_both_onnxruntime_keys(monkeypatch) -> None:
    """One ``EngineConfig.onnxruntime`` block feeds detection, classification and
    recognition alike — there is no per-model knob — and the values must be the
    clamped ones."""
    import rapidocr

    monkeypatch.setattr(rapidocr, "RapidOCR", _StubRapidOCR)
    _StubRapidOCR.last_params = None

    _reader(2)._load()

    assert _StubRapidOCR.last_params == {_INTRA: 2, _INTER: 2}


def test_load_caps_opencv_as_well(monkeypatch) -> None:
    """OpenCV resizes every image on the way in and defaults to one thread per
    core, so capping onnxruntime alone leaves the resize running wide."""
    import cv2
    import rapidocr

    monkeypatch.setattr(rapidocr, "RapidOCR", _StubRapidOCR)
    before = cv2.getNumThreads()
    try:
        _reader(2)._load()
        assert cv2.getNumThreads() == 2
    finally:
        cv2.setNumThreads(before)


@pytest.mark.skipif(
    not os.environ.get("TTB_OCR_MODELS"),
    reason="TTB_OCR_MODELS not set; skipping the OCR model load (rung 3)",
)
def test_every_built_session_reports_the_cap() -> None:
    """The proof: the three sessions are asked what they were built with.

    ``InferenceSession.get_session_options()`` reports the options the session is
    actually running under, so a value rapidocr dropped shows up here as the
    onnxruntime default of 0 rather than as the cap.
    """
    engine = _reader(2)._load()

    reported = {
        name: getattr(engine, name).session.session.get_session_options()
        for name in ("text_det", "text_cls", "text_rec")
    }
    for name, options in reported.items():
        assert options.intra_op_num_threads == 2, f"{name} intra_op not capped"
        assert options.inter_op_num_threads == 2, f"{name} inter_op not capped"
