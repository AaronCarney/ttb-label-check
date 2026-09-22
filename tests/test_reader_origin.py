"""The local reader finds an origin statement whose lead-in is set on two lines.

A centred label often stacks a short statement: "DISTILLED" on one line and
"IN IRELAND" under it. The engine returns each line as its own box, and a
lead-in read one box at a time is never whole. The first case is the geometry
the engine returned for ttb-26218001000369's front; the rest are the general
forms that must not be read as an origin.
"""

from __future__ import annotations

from app.vision.local import _Box, _parse


def _box(x0: float, y0: float, x1: float, y1: float, text: str, score: float = 0.99) -> _Box:
    return _Box(x0=x0, y0=y0, x1=x1, y1=y1, text=text, score=score)


def _origin(*boxes: _Box) -> tuple[dict, tuple[int, int, int, int] | None, str | None]:
    return _parse(boxes=list(boxes), warning_boxes=[], rotation=0)["country_origin"]


def test_a_lead_in_stacked_over_its_country_is_read() -> None:
    payload, bbox, text = _origin(
        _box(264, 668, 416, 711, "DISTILLED", 0.9999),
        _box(896, 672, 999, 711, "TRIPLE", 0.9999),
        _box(255, 707, 427, 744, "IN IRELAND", 0.9891),
        _box(874, 708, 1021, 745, "DISTILLED", 0.9999),
        _box(324, 757, 565, 866, "IRISH", 0.9996),
        _box(576, 759, 966, 865, "WHISKEY", 0.9999),
    )
    assert payload["country"] == "IRELAND"
    assert text == "DISTILLED IN IRELAND"
    # The evidence is both lines, and the confidence is the weaker line's.
    assert bbox == (255, 668, 427, 744)
    assert payload["confidence"] <= 0.9891


def test_one_line_is_still_read_as_it_was() -> None:
    payload, bbox, _text = _origin(_box(0, 0, 400, 30, "PRODUCT OF MEXICO"))
    assert payload["country"] == "MEXICO"
    assert bbox == (0, 0, 400, 30)


def test_lines_in_different_columns_are_not_joined() -> None:
    payload, _bbox, _text = _origin(
        _box(0, 0, 150, 40, "DISTILLED"),
        _box(600, 45, 780, 85, "IN IRELAND"),
    )
    assert payload["country"] == ""


def test_lines_a_paragraph_apart_are_not_joined() -> None:
    payload, _bbox, _text = _origin(
        _box(0, 0, 150, 40, "DISTILLED"),
        _box(0, 200, 180, 240, "IN IRELAND"),
    )
    assert payload["country"] == ""


def test_a_stacked_state_is_not_a_country() -> None:
    payload, _bbox, _text = _origin(
        _box(0, 0, 150, 40, "DISTILLED"),
        _box(0, 42, 180, 82, "IN KENTUCKY"),
    )
    assert payload["country"] == ""


def test_a_stacked_material_is_not_a_country() -> None:
    payload, _bbox, _text = _origin(
        _box(0, 0, 150, 40, "DISTILLED"),
        _box(0, 42, 180, 82, "FROM CORN"),
    )
    assert payload["country"] == ""


def test_a_whole_statement_on_one_line_does_not_run_on_into_the_next() -> None:
    """A registry label: the next line, joined on, made the State look like
    something else and slipped past the State filter."""
    payload, _bbox, _text = _origin(
        _box(0, 0, 300, 40, "DISTILLED IN INDIANA"),
        _box(0, 42, 300, 82, "CRUXDISTILLERY.COM"),
    )
    assert payload["country"] == ""


def test_a_lead_in_in_running_prose_is_not_joined_to_the_next_line() -> None:
    """A registry label's marketing paragraph, as the engine returned it: the
    lead-in ends one line of prose and the next line starts with words that
    are not a country."""
    payload, _bbox, _text = _origin(
        _box(
            96,
            367,
            733,
            402,
            "adventure. Cherish the memories with Belton Bridge bourbon, distilled in",
        ),
        _box(
            96,
            405,
            733,
            441,
            "small atches on copper pot stills from a mash of corn, rye, and barley. It",
        ),
    )
    assert payload["country"] == ""


def test_a_whole_lead_in_over_its_country_is_read() -> None:
    payload, _bbox, text = _origin(
        _box(0, 0, 200, 40, "PRODUCT OF"),
        _box(20, 42, 180, 82, "MEXICO"),
    )
    assert payload["country"] == "MEXICO"
    assert text == "PRODUCT OF MEXICO"
