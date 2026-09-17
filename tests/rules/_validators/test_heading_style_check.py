"""heading_style_check reads three things about the GOVERNMENT WARNING heading
and does not treat them alike.

The words and the capitals are read from the heading's own text, so getting
them wrong is the label's fault and §16.22(a)(2) makes it a rejection. Bold
weight is a stroke-width measurement taken on the heading's region of the
image, and the 2026-09-17 corpus sweep showed it moves with the photograph
rather than the typeface. So no measured weight rejects a label: where it does
not satisfy the rule the answer is insufficient evidence at warn severity under
the code the rule declares, and a reviewer decides.

Two payload shapes reach the validator, and the difference decides what each
may do. The reader emits `heading_all_caps` / `heading_bold` /
`heading_bold_measured_confident`, which is a measurement. Older hand-built
fixtures carry a `heading_styles` sub-object that *states* a weight as a fact
about the label, and a stated weight still rejects.
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
    return heading_style_check(
        obs, make_expected(field_id="warning_block"), rule or _rule(), make_context()
    )


def test_caps_and_bold_passes() -> None:
    obs = make_obs(
        field_id="warning_block",
        value={
            "heading_text": "GOVERNMENT WARNING",
            "heading_styles": {"weight": "bold", "case": "upper"},
        },
    )
    assert (
        heading_style_check(
            obs, make_expected(field_id="warning_block"), _rule(), make_context()
        ).outcome
        is Outcome.PASS
    )


def test_title_case_fails() -> None:
    obs = make_obs(
        field_id="warning_block",
        value={
            "heading_text": "Government Warning",
            "heading_styles": {"weight": "bold", "case": "title"},
        },
    )
    res = heading_style_check(obs, make_expected(field_id="warning_block"), _rule(), make_context())
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_not_bold_fails() -> None:
    obs = make_obs(
        field_id="warning_block",
        value={
            "heading_text": "GOVERNMENT WARNING",
            "heading_styles": {"weight": "regular", "case": "upper"},
        },
    )
    assert (
        heading_style_check(
            obs, make_expected(field_id="warning_block"), _rule(), make_context()
        ).outcome
        is Outcome.FAIL
    )


def test_unmeasured_weight_with_correct_capitals_goes_to_a_reviewer() -> None:
    """The reader could not measure the stroke width, and the capitals are right.

    Nothing about the label is known to be wrong, so this is not a rejection:
    the answer is insufficient evidence at warn severity, under the code the
    rule pack declares for it.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
            "heading_bold": False,
            "heading_bold_measured_confident": False,
        }
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == UNMEASURED_CODE


def test_unmeasured_weight_does_not_excuse_wrong_capitals() -> None:
    """Capitals are decided first, from the heading's own text, and still reject.

    A heading in title case is non-compliant whether or not anyone measured its
    weight, so the unmeasured branch must not swallow it.
    """
    res = _check(
        {
            "heading_text": "Government Warning:",
            "heading_all_caps": False,
            "heading_bold": True,
            "heading_bold_measured_confident": False,
        }
    )
    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_a_confident_measurement_of_not_bold_goes_to_a_reviewer() -> None:
    """A measured weight never rejects, even when the reader was confident.

    This test asserted the opposite until 2026-09-17, on the reasoning that a
    weight which *was* measured and came out regular is the label's fault. The
    corpus sweep in `eval/heading_bold_ratios.py` withdrew the premise: over the
    38 labels, all TTB-approved and so all required to be bold, the stroke-width
    ratio ran 0.111 to 0.508, and `ttb-26232001000404` measured 0.111 from a
    clean photograph and 0.261 from a blurred copy of the same printing. The
    measurement moves with the photograph, not the typeface, and the 0.25 cut
    called 18 of 28 approved labels not bold. A signal that wrong cannot carry a
    reject-severity verdict, so it carries a reviewer instead.
    See `docs/decisions.md#0037`.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
            "heading_bold": False,
            "heading_bold_measured_confident": True,
        }
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == UNMEASURED_CODE


def test_a_weight_the_payload_states_still_rejects() -> None:
    """The legacy sub-object asserts a weight; it does not measure one.

    This is the line the measured case is on the other side of. A hand-built
    fixture carrying `heading_styles: {"weight": "regular"}` is stating a fact
    about the label rather than reporting a stroke width taken off a
    photograph, so nothing about the corpus sweep touches it and it rejects.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING",
            "heading_styles": {"weight": "regular", "case": "upper"},
        }
    )
    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_a_payload_reporting_no_weight_at_all_goes_to_a_reviewer() -> None:
    """Silence about the weight is not a measurement of *not bold*.

    Both readers drop `heading_bold` when the stroke-width measurement was not
    taken, so a payload can carry the capitals and report no weight whatever.
    Read through the old `payload.get("heading_bold", False)` default that was
    a confident *not bold*, and with no `heading_bold_measured_confident` key to
    stop it — the unmeasured guard defaulted to "measured" — the label was
    rejected at reject severity for a weight nobody had reported. The module's
    own docstring has always said that must not happen.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
        }
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == UNMEASURED_CODE


def test_an_unconfident_measurement_claiming_bold_does_not_pass() -> None:
    """The same mistake in the other direction.

    An unconfident `HeadingMeasurement` reports `is_bold=False`, so a payload
    saying `heading_bold: True` alongside `heading_bold_measured_confident:
    False` is not something either reader produces — but treating a weight the
    reader disclaims as a satisfied requirement would pass a label on a
    measurement nobody took, which is the error this rule exists to avoid.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING:",
            "heading_all_caps": True,
            "heading_bold": True,
            "heading_bold_measured_confident": False,
        }
    )
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == UNMEASURED_CODE


def test_the_readers_own_keys_win_over_a_legacy_sub_object_beside_them() -> None:
    """One payload, two shapes, and only one of them is read.

    Which shape a payload is in used to be decided three times in this module,
    by three conditions that disagreed. It is decided once now, and this pins
    the answer: either reader key present means the reader's shape, and the
    legacy sub-object is not consulted even when it contradicts.
    """
    res = _check(
        {
            "heading_text": "GOVERNMENT WARNING",
            "heading_all_caps": False,
            "heading_bold": True,
            "heading_bold_measured_confident": True,
            "heading_styles": {"weight": "bold", "case": "upper"},
        }
    )
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_a_non_dict_style_report_is_not_a_style_report() -> None:
    """`heading_styles: null` reaches the validator from a hand-built fixture
    that meant "no styles". Reading `.get` off it raised `AttributeError` and
    took down the whole rule run; it now reads as no style report at all, and
    the payload is judged on the heading text it does carry."""
    res = _check({"heading_text": "GOVERNMENT WARNING", "heading_styles": None})
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_the_rule_pack_chooses_which_words_the_reader_must_report() -> None:
    """`required_case` and `required_weight` are the rule pack's, not constants.

    The reader reports booleans and this validator turns them into the words a
    pack names — `upper`/`lower`, `bold`/`regular`. Every shipped pack asks for
    upper and bold, so nothing exercised the other half of either mapping and a
    mutation run could swap the words with the suite still green.
    """
    lower_regular = make_rule(
        rule_id="common.warning.heading_caps_bold",
        cfr_citation="27 CFR §16.22(a)(2)",
        validator="heading_style_check",
        reason_code="WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
        match_policy=MatchPolicy.LAYOUT,
        parameters={
            "target_phrase": "GOVERNMENT WARNING",
            "required_case": "lower",
            "required_weight": "regular",
            "unmeasured_weight_reason_code": UNMEASURED_CODE,
        },
    )
    payload = {
        "heading_text": "GOVERNMENT WARNING",
        "heading_all_caps": False,
        "heading_bold": False,
        "heading_bold_measured_confident": True,
    }
    assert _check(payload, rule=lower_regular).outcome is Outcome.PASS
    # And the same payload against the pack this product ships fails on the
    # capitals, which is what says the two mappings are not the same word.
    assert _check(payload).outcome is Outcome.FAIL


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
    res = _check(
        {
            "heading_text": "GOVERNMENT  WARNING  :",
            "heading_all_caps": True,
            "heading_bold": True,
            "heading_bold_measured_confident": True,
        }
    )
    assert res.outcome is Outcome.PASS


def test_wrong_words_fail_however_well_they_are_printed() -> None:
    """The heading has to say what §16.21 says it says.

    Every other test here varies the capitals or the weight and leaves the
    words alone, so nothing asserted that the words are checked at all — a
    mutation run made `_phrase_and_case_ok` return True on a phrase mismatch
    and the whole suite stayed green. A label headed HEALTH ADVISORY in bold
    capitals is not carrying the mandated heading, and this is a reject-severity
    rule.
    """
    res = _check(
        {
            "heading_text": "HEALTH ADVISORY",
            "heading_all_caps": True,
            "heading_bold": True,
            "heading_bold_measured_confident": True,
        }
    )
    assert res.outcome is Outcome.FAIL
    assert res.severity is Severity.REJECT
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_only_the_separating_punctuation_is_ignored() -> None:
    """`_heading_phrase` strips the punctuation that separates the heading from
    the statement, and nothing else. A trailing colon is the regulation's own
    (`GOVERNMENT WARNING: (1) …`) and must pass; a trailing letter is a
    different word and must not. Without the second half, widening that strip
    set to swallow letters goes unnoticed."""
    styled = {
        "heading_all_caps": True,
        "heading_bold": True,
        "heading_bold_measured_confident": True,
    }
    assert _check({"heading_text": "GOVERNMENT WARNING:", **styled}).outcome is Outcome.PASS
    assert _check({"heading_text": "GOVERNMENT WARNINGX", **styled}).outcome is Outcome.FAIL


def test_a_style_report_with_no_heading_text_fails_rather_than_raising() -> None:
    """The legacy `heading_styles` shape means the reader found a heading, so
    the check does not fall through to `not_read_result`. If the payload then
    carries no `heading_text`, the words cannot match the target and the answer
    is a failure — not a TypeError from handing `None` to the normaliser, which
    is what this validator did when its default was anything but a string."""
    res = _check({"heading_styles": {"weight": "bold", "case": "upper"}})
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "WARNING.STYLE.HEADING_NOT_BOLD_CAPS"


def test_validator_registered() -> None:
    assert "heading_style_check" in VALIDATOR_REGISTRY
