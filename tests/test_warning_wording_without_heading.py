"""A face that carries the warning's wording but whose heading was not read.

The reader finds the government warning by its heading. Where it read the
statement's words and not the heading — a small image, a heading printed in a
face the engine mangles to "GOVERMMENT WARMIMQ" — the payload used to be the
same as a label that prints no warning at all, and `common.warning.present`
rejected it under §16.21. The wording is evidence the statement is there, and
the heading not being read is evidence about the reading, not the label, so all
three warning rules send it to a reviewer instead (FR-3, decision C).

Measured over every frozen face of both label sets: a face whose heading is
read holds 13 to 18 of the statement's 18 content words; a face with no
heading and no warning holds at most 4. Half the words is the line.
"""

from __future__ import annotations

from app.rules._validators.heading_style_check import heading_style_check
from app.rules._validators.presence_check import presence_check
from app.rules._validators.verbatim_hash import verbatim_hash
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from app.services.disposition import rule_disposition
from app.vision.faces import merge_readings
from app.vision.local import _Box, _parse, face_observations
from tests.rules.fixtures import make_context, make_expected, make_rule

HEADING_NOT_READ = "WARNING.HEADING.NOT_READ"

# The statement's lines as the engine returns them from a back label, with the
# heading misread past recognition.
_STATEMENT_LINES = [
    "GOVERMMENT WARMIMQ: (1) ACCORDING TO THE",
    "SURGEON GENERAL, WOMEN SHOULD NOT DRINK",
    "ALCOHOLIC BEVERAGES DURING PREGNANCY",
    "BECAUSE OF THE RISK OF BIRTH DEFECTS.",
    "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES",
    "IMPAIRS YOUR ABILITY TO DRIVE A CAR OR",
    "OPERATE MACHINERY, AND MAY CAUSE",
    "HEALTH PRORLEMS.",
]


def _lines(texts: list[str], *, top: float = 100.0) -> list[_Box]:
    return [
        _Box(x0=20.0, y0=top + 14.0 * i, x1=260.0, y1=top + 14.0 * i + 11.0, text=t, score=0.9)
        for i, t in enumerate(texts)
    ]


def _warning_payload(boxes: list[_Box]) -> tuple[dict, tuple | None, str | None]:
    return _parse(boxes=boxes, warning_boxes=boxes, rotation=0)["gov_warning"]


# --- the reader ---------------------------------------------------------------


def test_wording_with_no_heading_is_reported_as_such():
    boxes = [_Box(20.0, 20.0, 200.0, 50.0, "OLD FENCEPOST", 0.95), *_lines(_STATEMENT_LINES)]
    payload, bbox, text = _warning_payload(boxes)
    assert payload["wording_without_heading"] is True
    # Presence reads `text`, so the statement is not reported as found.
    assert payload["text"] == ""
    assert payload["heading_text"] == ""
    assert bbox is not None
    assert text and "SURGEON GENERAL" in text
    assert "OLD FENCEPOST" not in text


def test_a_face_with_a_few_warning_words_is_still_a_face_with_no_warning():
    """Label copy shares words with the statement — "DRINK RESPONSIBLY",
    "GENERAL MANAGER" — and a face with no warning holds up to 4 of them."""
    boxes = _lines(["PLEASE DRINK RESPONSIBLY", "HEALTH AND WELLNESS", "SURGEON GENERAL CIGARS"])
    payload, bbox, text = _warning_payload(boxes)
    assert "wording_without_heading" not in payload
    assert payload["text"] == ""
    assert bbox is None and text is None


def test_a_face_whose_heading_is_read_is_unchanged():
    lines = ["GOVERNMENT WARNING: (1) ACCORDING TO THE", *_STATEMENT_LINES[1:]]
    payload, _bbox, _text = _warning_payload(_lines(lines))
    assert "wording_without_heading" not in payload
    assert payload["text"].startswith("GOVERNMENT WARNING")


# --- the merge ----------------------------------------------------------------


def _face(boxes: list[_Box], tag: str) -> list[FieldObservation]:
    return face_observations(_parse(boxes=boxes, warning_boxes=boxes, rotation=0), face_tag=tag)


def _merged_warning(*faces: list[FieldObservation]) -> FieldObservation:
    return next(o for o in merge_readings(faces) if o.field_id == "gov_warning")


def test_the_face_whose_heading_was_read_wins_the_merge():
    """Its reading is the one the rules can judge, however cleanly the other
    face read the words."""
    heading_lines = ["GOVERNMENT WARNING: (1) ACCORDING TO THE", *_STATEMENT_LINES[1:]]
    headed = _lines(heading_lines)
    headed = [
        _Box(b.x0, b.y0, b.x1, b.y1, b.text, 0.6) for b in headed
    ]  # read less cleanly than the other face
    wording = _lines(_STATEMENT_LINES)
    merged = _merged_warning(_face(wording, "front"), _face(headed, "back"))
    assert merged.observed_value["text"].startswith("GOVERNMENT WARNING")


def test_wording_found_beats_a_face_that_found_nothing():
    wording = _lines(_STATEMENT_LINES)
    nothing = _lines(["OLD FENCEPOST", "KENTUCKY STRAIGHT BOURBON WHISKEY"])
    merged = _merged_warning(_face(nothing, "front"), _face(wording, "back"))
    assert merged.observed_value.get("wording_without_heading") is True


# --- the rules ----------------------------------------------------------------


def _observation() -> FieldObservation:
    payload, bbox, text = _warning_payload(_lines(_STATEMENT_LINES))
    return FieldObservation(
        field_id="gov_warning",
        beverage_class=BeverageClass.SPIRITS,
        observed_value=payload,
        evidence=(
            Evidence(
                field_id="gov_warning",
                source=EvidenceSource.OCR,
                panel="back",
                bbox=bbox,
                extracted_text=text,
                match_kind=MatchKind.NONE,
                confidence=float(payload["confidence"]),
            ),
        ),
    )


def _rule(validator: str, reason_code: str, **parameters):
    return make_rule(
        rule_id=f"common.warning.{validator}",
        cfr_citation="27 CFR §16.21",
        validator=validator,
        reason_code=reason_code,
        match_policy=MatchPolicy.EXACT,
        parameters={"heading_not_read_reason_code": HEADING_NOT_READ, **parameters},
    )


RULES = [
    (presence_check, _rule("presence_check", "WARNING.PRESENCE.MISSING", unlocated_is_absent=True)),
    (verbatim_hash, _rule("verbatim_hash", "WARNING.VERBATIM.MISMATCH")),
    (
        heading_style_check,
        _rule(
            "heading_style_check",
            "WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
            target_phrase="GOVERNMENT WARNING",
            required_case="upper",
            required_weight="bold",
        ),
    ),
]


def test_every_warning_rule_sends_it_to_a_reviewer():
    obs = _observation()
    for validator, rule in RULES:
        res = validator(obs, make_expected(field_id="gov_warning"), rule, make_context())
        assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE, rule.rule_id
        assert res.severity is Severity.WARN, rule.rule_id
        assert res.reason_code == HEADING_NOT_READ, rule.rule_id
        assert rule_disposition(res) == "needs_review", rule.rule_id
        assert res.message and "heading" in res.message, rule.rule_id


def test_a_label_with_neither_heading_nor_wording_still_fails():
    """Decision C: neither found on a face that was read stays a §16.21
    rejection. The new route must not have swallowed it."""
    payload, bbox, text = _warning_payload(_lines(["OLD FENCEPOST"]))
    obs = FieldObservation(
        field_id="gov_warning",
        beverage_class=BeverageClass.SPIRITS,
        observed_value=payload,
        evidence=(
            Evidence(
                field_id="gov_warning",
                source=EvidenceSource.OCR,
                panel="back",
                bbox=bbox,
                extracted_text=text,
                match_kind=MatchKind.NONE,
                confidence=0.0,
            ),
        ),
    )
    validator, rule = RULES[0]
    res = validator(obs, make_expected(field_id="gov_warning"), rule, make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.PRESENCE.MISSING"


def test_a_rule_that_declares_no_code_is_not_rescued():
    """The rule pack decides what the flag means. A rule naming no code keeps
    its own behaviour, as `unmeasured_weight_reason_code` does."""
    rule = make_rule(
        rule_id="common.warning.present",
        cfr_citation="27 CFR §16.21",
        validator="presence_check",
        reason_code="WARNING.PRESENCE.MISSING",
        parameters={"unlocated_is_absent": True},
    )
    res = presence_check(
        _observation(), make_expected(field_id="gov_warning"), rule, make_context()
    )
    assert res.outcome is Outcome.FAIL
