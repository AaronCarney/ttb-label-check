"""No result card may show a Python dict where a reviewer expects the label's words.

The card once read `Found: {'brand_name': 'Rossastro'}` beside
`Expected: FABIO SIGNORELLI`, because the envelope ran `str()` over the
reader's payload. The reader returns a dict per field (`_SCHEMAS` in
`app.vision.cloud`), so every field was one `str()` away from the same defect.

This test is driven off `_SCHEMAS` itself rather than a hand-listed set of
fields. A field added to the reader with no projection in
`app.services.reading_text._DISPLAY` fails here, instead of reaching a
reviewer as a repr.
"""

from __future__ import annotations

import pytest

from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import (
    Evidence,
    EvidenceSource,
    FieldObservation,
    MatchKind,
)
from app.services.envelope_builder import _FIELD_CANONICAL_TO_WIRE, build_field_findings
from app.vision.cloud import _SCHEMAS

# Punctuation that only appears in a repr of a Python container, never in the
# words a label prints.
_REPR_MARKS = ("{", "}", "': ", '": ')


def _sample_for(spec: dict) -> object:
    """A plausible reading for one schema property.

    The values are stand-ins; what is under test is the shape the reader
    promises, not any particular text.
    """
    types = spec.get("type")
    types = types if isinstance(types, list) else [types]
    if "string" in types:
        return "SOME TEXT"
    if "number" in types:
        return 12.5
    if "boolean" in types:
        return True
    raise AssertionError(f"unhandled schema type: {spec}")


def _payload_for(field_id: str) -> dict:
    """A full reading for one reader field, every declared property present."""
    props = _SCHEMAS[field_id]["properties"]
    return {key: _sample_for(spec) for key, spec in props.items()}


def _observation(field_id: str, payload: dict) -> FieldObservation:
    return FieldObservation(
        field_id=field_id,
        beverage_class=BeverageClass.SPIRITS,
        observed_value=payload,
        evidence=(
            Evidence(
                field_id=field_id,
                source=EvidenceSource.LAYOUT,
                match_kind=MatchKind.NONE,
                confidence=0.9,
            ),
        ),
        upstream_meta={},
    )


# Every reader field that reaches a card. `layout` is the page geometry the
# reader uses to find the others; it has no wire slot and no card.
_CARD_FIELDS = sorted(set(_SCHEMAS) & set(_FIELD_CANONICAL_TO_WIRE))


def test_every_reader_field_reaches_a_card():
    """A guard on the guard: if the mapping stops covering the reader, the
    loop below would silently test nothing."""
    uncovered = set(_SCHEMAS) - set(_FIELD_CANONICAL_TO_WIRE) - {"layout"}
    assert not uncovered, f"reader fields with no wire slot: {sorted(uncovered)}"
    assert len(_CARD_FIELDS) >= 7


@pytest.mark.parametrize("field_id", _CARD_FIELDS)
def test_card_value_carries_no_dict_repr(field_id: str):
    payload = _payload_for(field_id)
    findings = build_field_findings(
        results=(),
        observations=[_observation(field_id, payload)],
        expected_values=[ExpectedValue(field_id=field_id)],
    )
    slot = _FIELD_CANONICAL_TO_WIRE[field_id]
    card = next(f for f in findings if f.field_name == slot)
    shown = card.extracted_value
    for mark in _REPR_MARKS:
        assert mark not in shown, f"{slot} card shows a dict repr, not the label's words: {shown!r}"
    # A card that renders nothing is not a repr, but it is not the fix either:
    # every field here had a full reading.
    assert shown.strip(), f"{slot} card is empty for a complete reading"
