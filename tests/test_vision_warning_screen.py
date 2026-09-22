"""The strips are read before the label is read again.

`_has_sideways_text` says a label carries sideways text; it cannot say what
that text is, so it fires on a barcode and a net-contents line as readily as on
a warning printed up an edge. Each wrong guess costs two full detector passes —
about 875 ms on the development box, and several times that on the deployed
service, where it was enough to push one check past the reviewer's five
seconds.

So the strips the upright pass already found are read in place first, with
recognition alone and no second detection, and only a strip carrying the
warning's own words sends the re-read ahead. Measured over all 62 corpus
images (`docs/decisions.md#0036`): four reach this point, one carries the
warning, and the screen keeps the re-read on that one.

The screen answers yes wherever it cannot answer no, and the tests below hold
it to that: an unreadable strip and a label with no strips at all both re-read.
A wrong yes costs what this code used to cost every time; a wrong no is a
government warning nobody checked.

No OCR engine runs here except where one is named: the box lists and the strip
readings are supplied, and what is tested is what the reader asks for.
"""

from __future__ import annotations

from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from app.config import Settings
from app.rules._validators._helpers import normalize_words
from app.vision.local import _WARNING_SCREEN_WORDS, LocalVisionExtractor, _Box

ASSET = Path("assets/warnings/govt_warning_16_21.txt")


def _blank_label() -> bytes:
    image = Image.new("RGB", (900, 640), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _wide(y0: float, text: str = "BOTTLED BY SOMEONE") -> _Box:
    return _Box(x0=40, y0=y0, x1=520, y1=y0 + 48, text=text, score=0.95)


def _tall(x0: float, text: str = "GEN A L D DS D GES") -> _Box:
    """Text lying on its side. Its own text is what the upright pass made of
    it, which is why the screen re-reads the strip rather than trusting it."""
    return _Box(x0=x0, y0=30, x1=x0 + 52, y1=520, text=text, score=0.95)


def _reader(passes: list[list[_Box]], strips: list[str | None]) -> tuple[Any, list, list]:
    """A reader whose detector and strip reader both answer from a script.

    Returns the reader, the log of detector passes, and the log of strips read.
    """
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    calls: list = []
    read: list = []

    def fake_boxes(image):
        calls.append(image.size)
        return passes[min(len(calls) - 1, len(passes) - 1)]

    def fake_strip(image, box):
        read.append(box)
        return strips[min(len(read) - 1, len(strips) - 1)]

    reader._boxes = fake_boxes  # type: ignore[method-assign]
    reader._read_strip = fake_strip  # type: ignore[method-assign]
    return reader, calls, read


def test_strips_that_are_not_the_warning_stop_the_re_read() -> None:
    """A barcode up the edge of a label. The gate fires on its shape; the strip
    says what it is, and the two rotated passes are not paid for."""
    reader, calls, read = _reader([[_wide(100), _tall(700), _tall(780)]], ["3105540651"])

    reading = reader.look(_blank_label())

    assert len(calls) == 1, f"expected one detector pass, got {len(calls)}"
    assert len(read) == 2, "both strips are read before the warning is ruled out"
    assert reading.rotation == 0


def test_a_strip_carrying_the_warnings_words_sends_the_re_read_ahead() -> None:
    """The label the re-read exists for. One strip reads as the warning, and
    the rotated passes run as before."""
    reader, calls, read = _reader(
        [[_wide(100), _tall(700), _tall(780)]],
        ["THE SURGEON"],
    )

    reader.look(_blank_label())

    assert len(calls) == 3, f"expected the two rotated passes, got {len(calls) - 1}"
    assert len(read) == 1, "the first strip settled it; the second need not be read"


def test_a_truncated_strip_is_still_recognised_as_the_warning() -> None:
    """What the strips actually say on ttb-26212001000085. Recognition over a
    box the upright detector drew around vertical text clips the line, so the
    heading itself never comes back whole — the screen asks for the warning's
    words, not for its heading."""
    reader, calls, _ = _reader(
        [[_wide(100), _tall(700), _tall(780)]],
        ["DRIVE ACAR OROPERATEMACHINERY,ANDM"],
    )

    reader.look(_blank_label())

    assert len(calls) == 3, "a clipped warning line must still re-read"


def test_a_strip_that_cannot_be_read_re_reads() -> None:
    """No text came back from the strip. That is not evidence of absence, so
    the label is read again rather than passed over."""
    reader, calls, _ = _reader([[_wide(100), _tall(700), _tall(780)]], [None])

    reader.look(_blank_label())

    assert len(calls) == 3, "an unreadable strip must not rule the warning out"


def test_a_label_with_no_strips_re_reads() -> None:
    """Nothing tall enough to read. The screen has nothing to go on and says
    so; `_has_sideways_text` has already decided there is something here."""
    reader, _, _ = _reader([[]], [None])

    assert reader._sideways_may_be_the_warning(Image.new("RGB", (900, 640)), []) is True


def test_every_screen_word_is_in_the_16_21_text() -> None:
    """The screen's vocabulary against the asset it is drawn from. A word that
    drifts out of the statutory text costs a re-read that should have run, and
    a comment promising these match would not notice."""
    statutory = set(normalize_words(ASSET.read_text(encoding="utf-8")))

    missing = sorted(_WARNING_SCREEN_WORDS - statutory)

    assert not missing, f"not in {ASSET}: {missing}"


def _declined(caplog: Any) -> list:
    return [r for r in caplog.records if r.getMessage() == "sideways_reread_declined"]


def test_the_strips_declining_the_re_read_is_recorded(caplog: Any) -> None:
    """A label read upright only is reported as carrying no warning, and since
    the confidence-floor fix that is a rejection. So the decision not to look
    again is in the log, with which of the two screens declined."""
    reader, _, _ = _reader([[_wide(100), _tall(700), _tall(780)]], ["3105540651"])

    with caplog.at_level("INFO", logger="app.vision.local"):
        reader.look(_blank_label())

    records = _declined(caplog)
    assert len(records) == 1, f"expected one declined record, got {len(records)}"
    assert records[0].has_sideways_text is True, "the strips declined, not the box shapes"


def test_box_shapes_declining_the_re_read_is_recorded(caplog: Any) -> None:
    """No sideways boxes at all, so no strip is ever read. The same silence
    ends in the same rejection and is recorded the same way, told apart from
    the case above by `has_sideways_text`."""
    reader, _, read = _reader([[_wide(100), _wide(200)]], [None])

    with caplog.at_level("INFO", logger="app.vision.local"):
        reader.look(_blank_label())

    records = _declined(caplog)
    assert read == [], "no strip should be read when nothing is sideways"
    assert len(records) == 1, f"expected one declined record, got {len(records)}"
    assert records[0].has_sideways_text is False, "the box shapes declined"


def test_a_re_read_that_goes_ahead_is_not_recorded_as_declined(caplog: Any) -> None:
    """The signal marks a refusal to look, not a look that found nothing."""
    reader, _, _ = _reader(
        [[_wide(100), _tall(700), _tall(780)]],
        ["THE SURGEON"],
    )

    with caplog.at_level("INFO", logger="app.vision.local"):
        reader.look(_blank_label())

    assert _declined(caplog) == []


class _ScoringEngine:
    """Answers a recognition-only call with one text at a set score."""

    def __init__(self, text: str, score: float) -> None:
        self.text, self.score = text, score

    def __call__(self, image, use_det=None, use_cls=None, use_rec=None):
        return type("R", (), {"txts": [self.text], "scores": [self.score]})()


def _strip_read_at(score: float) -> str | None:
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    reader._engine = _ScoringEngine("GOANN ON OHNONOOI", score)  # type: ignore[assignment]
    strip = _Box(x0=100, y0=20, x1=140, y1=260, text="", score=0.9)
    return reader._read_strip(Image.new("RGB", (400, 300)), strip)


def test_a_strip_read_as_noise_cannot_rule_the_warning_out() -> None:
    """Small condensed type read strip by strip comes back as noise with no
    warning word in it, at a low recognition score — on seven held-out faces
    whose rotated pass reads the whole warning. A read that poor says nothing
    about what the strip is, so it counts as no read at all."""
    assert _strip_read_at(0.35) is None


def test_a_strip_read_cleanly_is_kept() -> None:
    """A strip read cleanly — a barcode, "750 ML" — is what lets the screen
    spare a label the two rotated passes, and a noisy but confident read of a
    non-warning line (0.567 on a corpus back label) is kept too."""
    assert _strip_read_at(0.567) == "GOANN ON OHNONOOI"
