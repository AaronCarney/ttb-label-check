"""A label where the warning was not found but some of its words were read.

`common.warning.present` is the one rule that reads the reader's silence as
the label's: no warning found is a §16.21 rejection. That silence is evidence
only where nothing of the statement was read. A face that shows "ABILITY TO
DRIVE" and no heading is a warning the reader could not find — printed too
small, curved round a can, cut off by the photograph — so the label goes to a
reviewer instead of being rejected for a warning it may carry.

Over the corpus's 26 faces with no warning found, none holds any of the
statement's content words. docs/decisions.md#0063.
"""

from __future__ import annotations

from app.rules._validators.presence_check import presence_check
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity
from app.services.disposition import rule_disposition
from app.vision.faces import merge_readings
from app.vision.local import _Box, _parse, face_observations
from tests.rules.fixtures import make_context, make_expected, make_rule

NOT_CONFIRMED = "WARNING.PRESENCE.NOT_CONFIRMED"


def _lines(texts: list[str]) -> list[_Box]:
    return [
        _Box(x0=20.0, y0=100.0 + 14.0 * i, x1=260.0, y1=111.0 + 14.0 * i, text=t, score=0.9)
        for i, t in enumerate(texts)
    ]


def _payload(boxes: list[_Box]) -> dict:
    return _parse(boxes=boxes, warning_boxes=boxes, rotation=0)["gov_warning"][0]


def _observation(boxes: list[_Box]) -> FieldObservation:
    payload, bbox, text = _parse(boxes=boxes, warning_boxes=boxes, rotation=0)["gov_warning"]
    return FieldObservation(
        field_id="gov_warning",
        beverage_class=BeverageClass.MALT,
        observed_value=payload,
        evidence=(
            Evidence(
                field_id="gov_warning",
                source=EvidenceSource.OCR,
                panel="front",
                bbox=bbox,
                extracted_text=text,
                match_kind=MatchKind.NONE,
                confidence=float(payload["confidence"]),
            ),
        ),
    )


def _rule(**parameters):
    return make_rule(
        rule_id="common.warning.present",
        cfr_citation="27 CFR §16.21",
        validator="presence_check",
        reason_code="WARNING.PRESENCE.MISSING",
        parameters={"unlocated_is_absent": True, **parameters},
    )


def _judge(boxes: list[_Box], **parameters):
    return presence_check(
        _observation(boxes),
        make_expected(field_id="gov_warning"),
        _rule(**parameters),
        make_context(),
    )


FRAGMENT = ["IPA 6.5% ALC/VOL", "YOUR ABILITY TO DRIVE A CAR"]


# --- the reader ---------------------------------------------------------------


def test_the_reader_reports_the_statement_words_it_read():
    payload = _payload(_lines(FRAGMENT))
    assert payload["warning_words_seen"] == ["ability", "drive"]
    assert payload["text"] == ""
    assert payload["confidence"] == 0.0


def test_a_face_with_none_of_the_words_reports_none():
    """Words the statement shares with every label ("your", "because") are not
    the statement's own and do not count."""
    payload = _payload(_lines(["OLD FENCEPOST", "BECAUSE YOUR TIME MATTERS"]))
    assert "warning_words_seen" not in payload


def test_the_face_with_the_words_wins_the_merge_over_a_face_with_none():
    def face(texts: list[str], tag: str):
        boxes = _lines(texts)
        return face_observations(_parse(boxes=boxes, warning_boxes=boxes, rotation=0), face_tag=tag)

    merged = merge_readings([face(["OLD FENCEPOST"], "front"), face(FRAGMENT, "back")])
    warning = next(o for o in merged if o.field_id == "gov_warning")
    assert warning.observed_value.get("warning_words_seen") == ["ability", "drive"]


# --- the rule -----------------------------------------------------------------


def test_words_seen_and_no_warning_found_goes_to_a_reviewer():
    res = _judge(_lines(FRAGMENT), words_seen_reason_code=NOT_CONFIRMED)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == NOT_CONFIRMED
    assert rule_disposition(res) == "needs_review"
    assert res.message and '"ability", "drive"' in res.message


def test_no_words_seen_is_still_a_missing_warning():
    res = _judge(_lines(["OLD FENCEPOST"]), words_seen_reason_code=NOT_CONFIRMED)
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.PRESENCE.MISSING"


def test_a_rule_that_declares_no_code_is_not_rescued():
    res = _judge(_lines(FRAGMENT))
    assert res.outcome is Outcome.FAIL
