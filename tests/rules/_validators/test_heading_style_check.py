"""heading_style_check reads three things about the GOVERNMENT WARNING heading
and does not treat them alike.

The words and the capitals are read from the heading's own text, so getting
them wrong is the label's fault and §16.22(a)(2) makes it a rejection. Bold
weight is a stroke-width measurement taken on the heading's region of the
image, and the reader cannot always take it. Reporting an unmeasured weight as
*not bold* would reject a label that may well be in bold for the product's own
blindness, so that branch answers insufficient evidence at warn severity under
the code the rule declares, and a reviewer decides.

Two payload shapes reach the validator. The reader emits
`heading_all_caps` / `heading_bold` / `heading_bold_measured_confident`; older
hand-built fixtures carry a `heading_styles` sub-object that states a weight
rather than measuring one, and is therefore read as measured.
"""
from __future__ import annotations

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.heading_style_check import heading_style_check
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

UNMEASURED_CODE = "WARNING.STYLE.BOLD_NOT_MEASURED"


def _rule(*, unmeasured_code: str | None = UNMEASURED_CODE):
    parameters = {
        "target_phrase": "GOVERNMENT WARNING",
        "required_case": "upper",
        "required_weight": "bold",
    }
    if unmeasured_code:
        parameters["unmeasured_weight_reason_code"] = unmeasured_code
    return make_rule(
        rule_id="common.warning.heading_caps_bold",
        cfr_citation="27 CFR §16.22(a)(2)",
        validator="heading_style_check",
        reason_code="WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
        match_policy=MatchPolicy.LAYOUT,
        parameters=parameters,
    )


def _check(payload: dict, *, rule=None):
    obs = make_obs(field_id="warning_block", value=payload)
    return heading_style_check(obs, make_expected(field_id="warning_block"), rule or _rule(), make_context())


def test_caps_and_bold_passes() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "GOVERNMENT WARNING", "heading_styles": {"weight": "bold", "case": "upper"}})
    assert heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.PASS


def test_title_case_fails() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "Government Warning", "heading_styles": {"weight": "bold", "case": "title"}})
    res = heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_not_bold_fails() -> None:
    obs = make_obs(field_id="warning_block", value={"heading_text": "GOVERNMENT WARNING", "heading_styles": {"weight": "regular", "case": "upper"}})
    assert heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context()).outcome is Outcome.FAIL


def test_unmeasured_weight_with_correct_capitals_goes_to_a_reviewer() -> None:
    """The reader could not measure the stroke width, and the capitals are right.

    Nothing about the label is known to be wrong, so this is not a rejection:
    the answer is insufficient evidence at warn severity, under the code the
    rule pack declares for it.
    """
    res = _check({
        "heading_text": "GOVERNMENT WARNING:",
        "heading_all_caps": True,
        "heading_bold": False,
        "heading_bold_measured_confident": False,
    })
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == UNMEASURED_CODE


def test_unmeasured_weight_does_not_excuse_wrong_capitals() -> None:
    """Capitals are decided first, from the heading's own text, and still reject.

    A heading in title case is non-compliant whether or not anyone measured its
    weight, so the unmeasured branch must not swallow it.
    """
    res = _check({
        "heading_text": "Government Warning:",
        "heading_all_caps": False,
        "heading_bold": True,
        "heading_bold_measured_confident": False,
    })
    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_measured_not_bold_still_fails() -> None:
    """A weight that was measured, and came out regular, is the label's fault."""
    res = _check({
        "heading_text": "GOVERNMENT WARNING:",
        "heading_all_caps": True,
        "heading_bold": False,
        "heading_bold_measured_confident": True,
    })
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_unmeasured_weight_without_a_declared_code_falls_through() -> None:
    """A rule that declares no code for this branch gets the old behaviour.

    There is no sentence to hand a reviewer without one, and a needs-review
    carrying no reason is worse than the weight the payload already holds.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
            "heading_bold": False,
            "heading_bold_measured_confident": False,
        },
        rule=_rule(unmeasured_code=None),
    )
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_spacing_inside_the_heading_is_not_a_difference() -> None:
    """ttb-26231001000662 prints `GOVERNMENT WARNING  :` and was approved."""
    res = _check({
        "heading_text": "GOVERNMENT  WARNING  :",
        "heading_all_caps": True,
        "heading_bold": True,
        "heading_bold_measured_confident": True,
    })
    assert res.outcome is Outcome.PASS


def test_validator_registered() -> None:
    assert "heading_style_check" in VALIDATOR_REGISTRY
