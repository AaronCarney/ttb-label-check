"""Every call names the stages it wants, because the engine remembers.

`RapidOCR.__call__` starts with `update_params`, and what it sets stays set on
the engine. One recognition-only call — which is what reading a strip is —
therefore leaves detection switched off for whoever calls next, and the next
caller is a different request being served by the one reader the process shares
(`app/deps.py`). The failure is silent: the engine returns an output object of
a different shape rather than raising, and a label comes back with nothing read
off it.

So both call sites pass all three flags rather than relying on a default.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from app.config import Settings
from app.vision.local import LocalVisionExtractor, _Box


@dataclass
class _Result:
    txts: list[str]
    scores: list[float]
    boxes: Any


@dataclass
class _RecordingEngine:
    """Answers like the engine, and keeps what each call asked for."""

    calls: list[dict] = field(default_factory=list)

    def __call__(self, image, use_det=None, use_cls=None, use_rec=None):
        self.calls.append({"use_det": use_det, "use_cls": use_cls, "use_rec": use_rec})
        quad = [[10.0, 10.0], [90.0, 10.0], [90.0, 30.0], [10.0, 30.0]]
        return _Result(txts=["SOMETHING"], scores=[0.9], boxes=np.array([quad]))


def _reader() -> tuple[LocalVisionExtractor, _RecordingEngine]:
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    engine = _RecordingEngine()
    reader._engine = engine  # type: ignore[assignment]
    return reader, engine


def test_a_full_pass_asks_for_all_three_stages() -> None:
    reader, engine = _reader()

    reader._boxes(Image.new("RGB", (400, 300), color=(255, 255, 255)))

    assert engine.calls == [{"use_det": True, "use_cls": True, "use_rec": True}]


def test_a_strip_read_asks_for_recognition_alone() -> None:
    reader, engine = _reader()
    image = Image.new("RGB", (400, 300), color=(255, 255, 255))

    text = reader._read_strip(image, _Box(x0=100, y0=20, x1=140, y1=260, text="", score=0.9))

    assert text == "SOMETHING"
    assert engine.calls == [{"use_det": False, "use_cls": True, "use_rec": True}]


def test_a_full_pass_after_a_strip_read_still_asks_to_detect() -> None:
    """The sequence a single check runs, and the one the defaults would break:
    strips first, then the rotated frame the screen let through."""
    reader, engine = _reader()
    image = Image.new("RGB", (400, 300), color=(255, 255, 255))

    reader._read_strip(image, _Box(x0=100, y0=20, x1=140, y1=260, text="", score=0.9))
    reader._boxes(image)

    assert engine.calls[-1]["use_det"] is True
    assert engine.calls[-1]["use_rec"] is True


def test_a_strip_read_without_an_engine_says_it_could_not_read() -> None:
    """`None` rather than an exception: the caller treats it as "cannot rule
    the warning out" and reads the label again."""
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())

    assert reader._engine is None
    assert (
        reader._read_strip(
            Image.new("RGB", (400, 300)),
            _Box(x0=100, y0=20, x1=140, y1=260, text="", score=0.9),
        )
        is None
    )
