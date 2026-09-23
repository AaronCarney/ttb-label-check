"""The rotated re-read runs where there is sideways text, and nowhere else.

Where the upright pass finds no government-warning heading, the reader turns
the image on its side both ways and reads it again. Those two extra passes are
the most expensive thing a read can do — a full detector pass each — and they
produce exactly one field: `warning_boxes` feeds the warning and nothing else,
because the other six fields are cut from the upright pass whatever the rotated
frames turn up.

Most labels have no warning on the face submitted, so the re-read finds nothing
and the cost buys nothing: over the project's corpus it ran on 35 images and
recovered a warning from one. So it runs only where the upright pass has
already shown sideways text — tall narrow boxes where upright text is wide.

No OCR engine runs here. The box list the engine would return is supplied
directly, and what is being tested is how many times the reader asks for one.
"""

from __future__ import annotations

from collections import deque
from io import BytesIO

from PIL import Image

from app.config import Settings
from app.vision.local import LocalVisionExtractor, _Box

_HEADING = "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON"


def _blank_label() -> bytes:
    """An image for the reader to open. Its pixels are never read here: every
    box the reader sees is supplied by the stub below."""
    image = Image.new("RGB", (900, 640), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _wide(y0: float, text: str = "BOTTLED BY SOMEONE") -> _Box:
    """Upright text: wider than it is tall, as the detector reports it."""
    return _Box(x0=40, y0=y0, x1=520, y1=y0 + 48, text=text, score=0.95)


def _tall(x0: float, text: str = "ALCOHOLIC BEVERAGES IMPAIRS YOUR") -> _Box:
    """Text lying on its side: a tall narrow strip."""
    return _Box(x0=x0, y0=30, x1=x0 + 52, y1=520, text=text, score=0.95)


def _reader_returning(*passes: list[_Box]) -> tuple[LocalVisionExtractor, list]:
    """A reader whose detector returns a prepared list per call, and the log of
    the calls made. The last list is repeated if the reader asks again."""
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    calls: list = []

    def fake_boxes(image):
        calls.append(image.size)
        return passes[min(len(calls) - 1, len(passes) - 1)]

    reader._boxes = fake_boxes  # type: ignore[method-assign]
    return reader, calls


def test_upright_text_without_a_warning_is_read_once() -> None:
    """The common case: a front label, no warning on it, nothing sideways.

    One detector pass. Before the gate this cost three.
    """
    reader, calls = _reader_returning([_wide(100), _wide(200), _wide(300)])

    reading = reader.look(_blank_label())

    assert len(calls) == 1, f"expected one detector pass, got {len(calls)}"
    assert reading.rotation == 0


def test_several_tall_boxes_bring_the_rotated_passes_back() -> None:
    """A warning printed sideways up an edge detects as tall strips, and the
    re-read is what recovers it. Both angles are tried when neither finds a
    heading."""
    reader, calls = _reader_returning([_wide(100), _tall(700), _tall(780)])

    reader.look(_blank_label())

    assert len(calls) == 3, f"expected the two rotated passes, got {len(calls) - 1}"


def test_one_very_tall_box_is_enough_to_re_read() -> None:
    """A single sideways line comes back as one long strip and nothing else,
    so the count of tall boxes never reaches two. The strip's own shape is
    what settles it."""
    lone = _Box(x0=700, y0=30, x1=744, y1=520, text="IMPAIRS YOUR ABILITY", score=0.95)
    reader, calls = _reader_returning([_wide(100), _wide(200), lone])

    reader.look(_blank_label())

    assert len(calls) == 3, f"expected the two rotated passes, got {len(calls) - 1}"


def _statement(y0: float, *lines: str) -> list[_Box]:
    """The warning as a rotated frame reads it: one upright line per box."""
    return [
        _Box(x0=20, y0=y0 + 50 * i, x1=600, y1=y0 + 50 * i + 46, text=line, score=0.98)
        for i, line in enumerate(lines)
    ]


_WHOLE = (
    _HEADING,
    "GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY",
    "BECAUSE OF THE RISK OF BIRTH DEFECTS. (2) CONSUMPTION OF ALCOHOLIC",
    "BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR OPERATE MACHINERY,",
    "AND MAY CAUSE HEALTH PROBLEMS.",
)


def test_the_warning_the_re_read_recovers_is_still_recovered() -> None:
    """The case the whole retry exists for, end to end: nothing upright, tall
    strips present, and the heading found once the frame is turned. The reading
    records the angle, and the warning is read from that frame's boxes."""
    upright = [_wide(100), _tall(700), _tall(780)]
    rotated = _statement(190, *_WHOLE)
    reader, calls = _reader_returning(upright, rotated)

    reading = reader.look(_blank_label())

    assert len(calls) == 2, "the first angle read the whole statement; the second must not run"
    assert reading.rotation == 270, "270° is tried first"
    assert reading.warning_boxes == rotated
    # The other six fields are cut from the upright pass, untouched by the turn.
    assert reading.boxes == upright


def test_a_label_lying_on_its_side_is_still_turned() -> None:
    """A whole label photographed sideways detects as tall boxes throughout —
    the other thing the re-read exists for, and the one a gate keyed on the
    warning alone would miss."""
    reader, calls = _reader_returning([_tall(x) for x in (100, 200, 300, 400)])

    reader.look(_blank_label())

    assert len(calls) == 3, f"expected the two rotated passes, got {len(calls) - 1}"


def test_a_heading_alone_does_not_stop_the_other_angle() -> None:
    """One frame can find the heading line and nothing under it, while the
    other angle reads the whole statement: on four held-out labels the loop
    stopped at the heading and the warning was checked against one line of it.
    A frame is final only when its block reaches the statement's last words;
    otherwise the other angle is read and the more complete block is kept."""
    upright = [_wide(100), _tall(700), _tall(780)]
    heading_only = _statement(190, _HEADING)
    whole = _statement(190, *_WHOLE)
    reader, calls = _reader_returning(upright, heading_only, whole)

    reading = reader.look(_blank_label())

    assert len(calls) == 3, "the 90° pass must run when 270° read only the heading"
    assert reading.rotation == 90
    assert reading.warning_boxes == whole


def test_neither_angle_complete_keeps_the_one_that_read_more() -> None:
    """Where neither frame reaches the end, the block holding more of the
    statement's words is kept, and a tie keeps the first angle tried, so the
    same boxes always give the same frame."""
    upright = [_wide(100), _tall(700), _tall(780)]
    more = _statement(190, *_WHOLE[:3])
    less = _statement(190, _HEADING)
    reader, calls = _reader_returning(upright, more, less)

    reading = reader.look(_blank_label())

    assert len(calls) == 3
    assert reading.rotation == 270
    assert reading.warning_boxes == more

    reader, _ = _reader_returning(upright, less, less)
    assert reader.look(_blank_label()).rotation == 270, "a tie keeps the first angle"
