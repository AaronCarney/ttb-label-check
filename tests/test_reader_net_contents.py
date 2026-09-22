"""The local reader returns the net contents the bottle declares, not every
volume printed on the label.

A label prints other volumes: the barrel the spirit aged in, the serving size in
a Serving Facts panel (TTB Ruling 2013-2, voluntary and not the net contents),
and a history line. Each case below is the text the OCR engine returned for a
real approved label, or the general form of one.
"""

from __future__ import annotations

import pytest

from app.vision.local import _Box, _parse


def _box(x0: float, y0: float, x1: float, y1: float, text: str, score: float) -> _Box:
    return _Box(x0=x0, y0=y0, x1=x1, y1=y1, text=text, score=score)


def _net(*boxes: _Box) -> dict:
    return _parse(boxes=list(boxes), warning_boxes=[], rotation=0)["net_contents"][0]


@pytest.mark.parametrize(
    "line",
    [
        # ttb-26230001000540, back
        "IN 53 GALLON CHARRED",
        "aged in 200 L casks",
        "matured in new 53 gallon American oak barrels",
        "53-gallon barrels",
        # ttb-26236001000448, back
        "Serving Facts: Serving Size: 1.5 fl oz (44 ml); Servings per",
        "Serving size 1.5 fl oz (44 mL)",
        # ttb-24026001000070, front: two lines of the same history paragraph.
        "In 1838 The 15-Gallon Act was passed",
        "any quantity under 15 gallons. That year,",
        "0.6 fl oz of alcohol",
    ],
)
def test_a_volume_that_is_not_the_bottles_contents_is_not_read(line: str) -> None:
    payload = _net(_box(0.0, 0.0, 600.0, 30.0, line, 0.99))
    assert payload["net_contents_value"] is None
    assert payload["confidence"] == 0.0


@pytest.mark.parametrize(
    ("line", "value", "unit"),
    [
        ("750 ML", 750.0, "ML"),
        ("45% ALC/VOL • 90 PROOF • 750 mL", 750.0, "mL"),
        ("40% ALC BY VOL | 750 mL| GLUTEN FREE", 750.0, "mL"),
        ("NET CONTENTS 750 ML", 750.0, "ML"),
        ("15.5 US GALLONS", 15.5, "US GALLONS"),
        ("BARREL PROOF 750 ML", 750.0, "ML"),
        ("750 ML BARREL PROOF", 750.0, "ML"),
        ("750 ML I117 Proof I 58.5% Alc/vol", 750.0, "ML"),
        ("Contains 750 ml", 750.0, "ml"),
    ],
)
def test_the_bottles_contents_are_still_read(line: str, value: float, unit: str) -> None:
    payload = _net(_box(0.0, 0.0, 600.0, 30.0, line, 0.99))
    assert payload["net_contents_value"] == value
    assert payload["unit"] == unit


def test_the_contents_are_found_past_a_barrel_size_on_the_same_face() -> None:
    payload = _net(
        _box(0.0, 0.0, 600.0, 30.0, "AGED 4 YEARS IN 53 GALLON CHARRED OAK", 0.99),
        _box(0.0, 40.0, 200.0, 70.0, "750 mL", 0.95),
    )
    assert payload["net_contents_value"] == 750.0


def test_a_serving_size_split_from_its_lead_in_is_still_not_read() -> None:
    # The Serving Facts panel read as two boxes on one line.
    payload = _net(
        _box(0.0, 0.0, 160.0, 30.0, "Serving Size", 0.99),
        _box(170.0, 0.0, 420.0, 30.0, "1.5 fl oz (44 mL)", 0.99),
    )
    assert payload["net_contents_value"] is None
