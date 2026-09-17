"""Generated inputs against the unit parser, which is where a live defect lived.

Decision `0008` records the shape: a label reading `12 FL. OZ.` normalised to
`FLOZ`, never matched the `fl oz` row of the table, and was compared as 12
millilitres against 355 — rejecting a compliant label. One example test fixes
one spelling. A property says the thing that actually has to be true: **however
a label punctuates, spaces or cases a unit the table lists, the same quantity
comes back.**

These generate their spellings from the shipped table rather than from a list
written here, so a unit added to `rules/tables/volume_units.yaml` is covered the
day it is added rather than the day someone remembers to add a case.
"""

from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.rules.units import (
    UnitTable,
    millilitres,
    millilitres_from_text,
    shipped_table,
    unit_key,
)

RULES_ROOT = Path("rules")


@pytest.fixture(scope="module")
def table() -> UnitTable:
    loaded = shipped_table(RULES_ROOT)
    assert loaded.factors, "the shipped units table is empty, so nothing below tests anything"
    return loaded


def _convertible_units(table: UnitTable) -> list[str]:
    """Keys the table can actually convert. A key listed with no factor is a
    reviewer's question by design, so it is not a case for these properties."""
    return sorted(key for key, factor in table.factors.items() if factor is not None)


# How a label may write a unit: any mix of case, and any of the separators a
# printed label uses between or after the letters. Every one of these must
# reduce to the same key, because `normalize_words` treats anything that is not
# a letter or a digit as a break.
_SEPARATORS = st.sampled_from(["", " ", ".", ". ", " . ", "  ", "-", "/"])


@st.composite
def _spelling_of(draw, key: str) -> str:
    """One key, written the way a label might print it."""
    # Split the key into pieces and rejoin them with printed separators.
    cut = draw(st.integers(min_value=1, max_value=max(1, len(key) - 1)))
    head, tail = key[:cut], key[cut:]
    joined = head + draw(_SEPARATORS) + tail + draw(_SEPARATORS)
    return "".join(
        draw(st.sampled_from([ch.upper(), ch.lower()])) if ch.isalpha() else ch for ch in joined
    )


@given(text=st.text())
def test_unit_key_is_idempotent(text):
    """Reducing an already-reduced unit changes nothing.

    If it did, whether two spellings matched would depend on how many times
    each had been through the reduction.
    """
    once = unit_key(text)
    assert unit_key(once) == once


@given(data=st.data())
@settings(max_examples=200, deadline=None)
def test_every_printed_spelling_of_a_listed_unit_reduces_to_the_same_key(data, table):
    key = data.draw(st.sampled_from(_convertible_units(table)))
    spelling = data.draw(_spelling_of(key))
    assert unit_key(spelling) == key, (
        f"{spelling!r} does not reduce to {key!r}, so a label printing it that way "
        f"would not match the table"
    )


@given(
    data=st.data(),
    amount=st.floats(min_value=0.001, max_value=1_000_000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=None)
def test_a_listed_unit_converts_by_its_own_factor(data, amount, table):
    key = data.draw(st.sampled_from(_convertible_units(table)))
    spelling = data.draw(_spelling_of(key))
    factor = table.factors[key]
    assert factor is not None
    assert millilitres(amount, spelling, table) == pytest.approx(amount * factor)


@given(
    data=st.data(),
    amount=st.integers(min_value=1, max_value=10_000),
)
@settings(max_examples=200, deadline=None)
def test_a_declared_text_of_one_figure_and_one_unit_converts(data, amount, table):
    """This is the live defect's own shape: one number, one unit, one answer."""
    key = data.draw(st.sampled_from(_convertible_units(table)))
    spelling = data.draw(_spelling_of(key))
    # A separator between figure and unit, as a label prints it.
    gap = data.draw(st.sampled_from(["", " ", "  "]))
    text = f"{amount}{gap}{spelling}"
    # A spelling whose separator leaves a digit adjacent to the figure would
    # change which number is being read, and no label prints one.
    assume(not spelling[:1].isdigit())
    factor = table.factors[key]
    assert factor is not None
    assert millilitres_from_text(text, table) == pytest.approx(amount * factor)


@given(text=st.text(max_size=200))
@settings(max_examples=300, deadline=None)
def test_reading_a_declared_text_never_raises(text, table):
    """A label may print anything at all, and the reader hands whatever it read
    straight to this. Refusing to answer is allowed; falling over is not,
    because the exception is the whole evaluation rather than one field."""
    result = millilitres_from_text(text, table)
    assert result is None or isinstance(result, float)


@given(amount=st.floats(allow_nan=False, allow_infinity=False), unit=st.text(max_size=20))
@settings(max_examples=200, deadline=None)
def test_an_unlistable_unit_answers_none_rather_than_a_number(amount, unit, table):
    """A unit the table cannot convert leaves nothing to compare, and the whole
    design turns on that being a reviewer's question rather than a guess."""
    assume(not table.lists(unit))
    assert millilitres(amount, unit, table) is None
