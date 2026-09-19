"""The label reading as a reviewer reads it, for the result page.

The engine and the reviewer want two different projections of the same
observation, and conflating them is what put a Python dict on the result page.

`project_reading` in `app/rules/_validators/_helpers.py` is the engine's: one
string per field, reduced to whatever the rule compares. For alcohol content
that is the number alone, because the rule compares a percentage against a
tolerance; for net contents it is the quantity without its unit, for the same
reason.

A reviewer is checking a photograph against an application. What helps them is
the statement as the label prints it — "ALC 13.5% BY VOL.", "750 ML" — not the
figure the comparison reduced it to. So this projection keeps the units and
prefers the reader's own text where it captured it.

Neither projection may be a `str()` of the payload. The reader returns a dict
per field (`_SCHEMAS` in `app/vision/cloud.py`), so `str()` yields
`{'brand_name': 'Patria'}`, which a reviewer cannot compare against anything.
"""

from __future__ import annotations

from typing import Any

# Keys that describe a reading rather than being one, so a payload holding only
# metadata reads as empty rather than as its own bookkeeping.
_METADATA_KEYS = frozenset({"confidence", "page_id", "panel", "bbox"})


def _number(value: Any) -> str:
    """A quantity without a trailing `.0` it never had on the label."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _joined(value: dict, keys: tuple[str, ...], separator: str = ", ") -> str:
    """The named keys, in order, dropping the ones the reader left unset."""
    parts = [str(value[k]).strip() for k in keys if value.get(k) is not None]
    return separator.join(p for p in parts if p)


def _alcohol(value: dict) -> str:
    """The alcohol statement as printed, or the figure if that is all there is."""
    printed = str(value.get("alc_text") or "").strip()
    if printed:
        return printed
    percentage = value.get("abv_pct")
    if percentage is None:
        return ""
    return f"{_number(percentage)}{str(value.get('unit') or '%').strip()}"


def _warning(value: dict) -> str:
    """The warning as printed. The heading is normally the first words of the
    text itself; where the reader recorded it separately and it is not already
    in the text, it goes in front, because the heading is half of what a
    reviewer is checking (§16.22(a)(2)) and a card that hides it is hiding the
    thing under review. Whether the heading is capitalised and bold is a
    verdict, reported by `common.warning.heading_caps_bold` with its own
    explanation, not a value to print here."""
    text = str(value.get("text") or "").strip()
    heading = str(value.get("heading_text") or "").strip()
    if heading and heading.upper() not in text.upper():
        return f"{heading} {text}".strip()
    return text


def _net_contents(value: dict) -> str:
    """The quantity with its unit, which is how a label states it."""
    quantity = value.get("net_contents_value")
    if quantity is None:
        return ""
    unit = str(value.get("unit") or "").strip()
    return f"{_number(quantity)} {unit}".strip()


# One entry per wire field slot, since that is what the result page shows.
_DISPLAY: dict[str, Any] = {
    "brand_name": lambda v: _joined(v, ("brand_name",)),
    "class_type": lambda v: _joined(v, ("class_type",)),
    "alcohol_content": _alcohol,
    "net_contents": _net_contents,
    "warning": _warning,
    "name_address": lambda v: _joined(v, ("name", "city", "state")),
    "country_of_origin": lambda v: _joined(v, ("country",)),
}


def reading_for_display(wire_slot: str, value: Any) -> str:
    """One observation as the words a reviewer compares against the application.

    `wire_slot` is the `FieldFindingWire.field_name` the observation lands in.
    A bare string passes through, so a hand-built fixture keeps working. A
    payload for a slot with no entry falls back to its own non-metadata keys,
    which is the same fallback the engine's projection uses: a new field shows
    a reviewer something readable before anyone teaches this table about it.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return str(value).strip()
    project = _DISPLAY.get(wire_slot)
    if project is not None:
        return project(value)
    return _joined(value, tuple(k for k in value if k not in _METADATA_KEYS))
