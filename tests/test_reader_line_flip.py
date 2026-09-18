"""The reader turns a line upside down only when it is all but certain the line is.

rapidocr runs a 0/180 orientation classifier over every line it detects and
flips the line when the classifier's confidence clears ``Cls.cls_thresh``,
0.9 by default. On this corpus that default flips upright lines of the health
warning, and a flipped line reads as noise: ``ttb-26218001000369`` reads its
warning 131 characters away from §16.21 at 0.9 and exactly at 0.999, and is
rejected under ``common.warning.verbatim`` for it. The measurement and the
choice of 0.999 are in ``docs/decisions.md#0039``.

The first test loads no model. The second reads a real label, so it is skipped
unless ``TTB_OCR_MODELS`` is set, the shape ``tests/test_vision_thread_cap.py``
uses.
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

import pytest

from app.config import Settings
from app.rules._validators.verbatim_hash import canonicalize_text
from app.vision.local import LINE_FLIP_CONFIDENCE, LocalVisionExtractor, _parse

_LABELS = Path(__file__).parent / "fixtures" / "labels"
_CANON = (Path(__file__).parents[1] / "assets/warnings/govt_warning_16_21.txt").read_text()


class _StubRapidOCR:
    last_params: dict | None = None

    def __init__(self, params: dict | None = None) -> None:
        type(self).last_params = params


def _reader() -> LocalVisionExtractor:
    return LocalVisionExtractor(settings=Settings(ocr_num_threads=2), ring_buffer=deque())


def test_the_engine_is_built_with_the_strict_flip_threshold(monkeypatch) -> None:
    import rapidocr

    monkeypatch.setattr(rapidocr, "RapidOCR", _StubRapidOCR)
    _StubRapidOCR.last_params = None

    _reader()._load()

    assert LINE_FLIP_CONFIDENCE == 0.999
    assert _StubRapidOCR.last_params is not None
    assert _StubRapidOCR.last_params["Cls.cls_thresh"] == LINE_FLIP_CONFIDENCE


@pytest.mark.skipif(
    not os.environ.get("TTB_OCR_MODELS"),
    reason="TTB_OCR_MODELS not set; skipping the OCR model load",
)
def test_a_warning_the_default_threshold_garbled_reads_exactly() -> None:
    reader = _reader()
    reader._engine = reader._load()

    reading = reader.look((_LABELS / "26218001000369" / "back.jpg").read_bytes())
    found = _parse(
        boxes=reading.boxes,
        warning_boxes=reading.warning_boxes,
        rotation=reading.rotation,
        heading_measurement=reading.heading_measurement,
    )["gov_warning"]

    assert canonicalize_text(found[0]["text"]) == canonicalize_text(_CANON)
