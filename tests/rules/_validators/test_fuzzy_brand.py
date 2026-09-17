"""fuzzy_brand routes one label brand mark against every name the application
says the label may carry.

The admissible set is the declared brand, the fanciful name, and any trade
name the application marks "(Used on label)". Four routes run in order —
exact, whole words, score, and the review-only first-letter route — and the
result names which admissible value matched, so a reviewer looking at a label
whose mark is not the brand field's wording is told where that name came from.

The first-letter route is the one design here that must not be simplified: it
can reach a reviewer and never a match. Folding it into one score and taking
the maximum would make "Gin" against "Din" a perfect score and a clean pass on
a three-letter brand whose only distinguishing letter differs.
"""

from __future__ import annotations

import pytest

from app.rules._validators import VALIDATOR_REGISTRY
from app.rules._validators.fuzzy_brand import fuzzy_brand
from app.rules.brand_match import stage_b_fuzzy
from app.schemas.rejection import Outcome, Severity
from app.schemas.rules import MatchPolicy
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

PASS_THRESHOLD = 0.92
NEEDS_REVIEW_THRESHOLD = 0.85


def _rule():
    return make_rule(
        rule_id="brand.match",
        cfr_citation="27 CFR §4.33",
        validator="fuzzy_brand",
        reason_code="BRAND.NAME.MISMATCH",
        match_policy=MatchPolicy.FUZZY,
        parameters={
            "pass_threshold": PASS_THRESHOLD,
            "needs_review_threshold": NEEDS_REVIEW_THRESHOLD,
            "needs_review_reason_code": "BRAND.NAME.NEEDS_REVIEW",
        },
    )


def _verdict(label_brand, declared, **parameters):
    obs = make_obs(field_id="brand", value=label_brand)
    exp = make_expected(field_id="brand", value=declared, parameters=parameters or None)
    return fuzzy_brand(obs, exp, _rule(), make_context())


# ---------------------------------------------------------------------------
# The admissible set
# ---------------------------------------------------------------------------


def test_the_declared_brand_matches_plainly_and_says_nothing_more() -> None:
    res = _verdict("STONE'S THROW", "Stone's Throw")
    assert res.outcome is Outcome.PASS
    assert res.message is None


def test_a_trade_name_used_on_the_label_is_a_match() -> None:
    """TACONIC DISTILLERY filed the application; the bottle says BONEFISH, and
    the application itself lists BONEFISH as used on the label."""
    res = _verdict(
        "BONEFISH",
        "TACONIC DISTILLERY",
        trade_names_used_on_label=("BONEFISH",),
    )
    assert res.outcome is Outcome.PASS
    assert res.message and "BONEFISH" in res.message, res.message


def test_the_match_names_which_value_it_matched() -> None:
    """The reviewer sees a label whose mark is not the brand field's wording,
    so the finding has to say where that name came from."""
    res = _verdict(
        "BONEFISH",
        "TACONIC DISTILLERY",
        trade_names_used_on_label=("BONEFISH",),
    )
    assert "used on the label" in res.message, res.message


def test_a_fanciful_name_is_a_match() -> None:
    res = _verdict("EKSTRA", "SVYTURYS", fanciful_name="EKSTRA")
    assert res.outcome is Outcome.PASS
    assert res.message and "fanciful" in res.message, res.message


def test_a_mark_that_is_a_word_run_of_the_declared_brand_is_a_match() -> None:
    """THE UGLY on the label, UGLY SWEATER in the application: the mark is the
    declared brand with a word left off and an article in front."""
    res = _verdict("THE UGLY", "UGLY SWEATER")
    assert res.outcome is Outcome.PASS
    assert res.message and "UGLY SWEATER" in res.message


def test_a_trade_name_does_not_rescue_an_unrelated_mark() -> None:
    res = _verdict("Bizmark", "Acme", trade_names_used_on_label=("Acme Spirits",))
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.NAME.MISMATCH"


# ---------------------------------------------------------------------------
# Scores and thresholds
# ---------------------------------------------------------------------------


def test_a_near_spelling_above_the_threshold_matches() -> None:
    res = _verdict("Stones Throw Bourbon", "Stone's Throw Bourbon")
    assert res.outcome is Outcome.PASS
    assert res.message and "0.9" in res.message


def test_the_borderline_band_reports_needs_review() -> None:
    """Calibrated inputs: if a later normalisation change drifts them out of
    the band, skip with the measured number rather than silently
    reclassifying. tests/test_brand_match_policies.py covers the same contract
    with its own pair and its own calibration step."""
    label_brand, declared = "Acme Brewing Company", "Acme Brewer Company"
    score = stage_b_fuzzy(label_brand, declared)
    if not (NEEDS_REVIEW_THRESHOLD <= score < PASS_THRESHOLD):
        pytest.skip(
            f"borderline calibration drifted: stage_b_fuzzy={score:.4f} "
            f"outside [{NEEDS_REVIEW_THRESHOLD}, {PASS_THRESHOLD}); "
            "retune the input pair or the normalisation"
        )
    res = _verdict(label_brand, declared)
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "BRAND.NAME.NEEDS_REVIEW"


def test_a_different_name_below_the_floor_fails() -> None:
    res = _verdict("Acme", "Bizmark")
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.NAME.MISMATCH"


# ---------------------------------------------------------------------------
# The first-letter route
# ---------------------------------------------------------------------------


def test_a_misread_first_letter_reaches_a_reviewer() -> None:
    """The label's script logo reads Gallo; the registry record spells it
    QALIO. Scored straight, that is 0.7333 and a rejection of a label TTB
    approved."""
    res = _verdict("Gallo", "QALIO")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "BRAND.NAME.NEEDS_REVIEW"
    assert res.message and "first character" in res.message


def test_the_first_letter_route_can_never_report_a_match() -> None:
    """The whole design. "Gin" and "Din" are identical after their first
    character, so a route that could pass on that score would clear a
    three-letter brand whose only distinguishing letter is wrong."""
    res = _verdict("Gin", "Din")
    assert res.outcome is not Outcome.PASS
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.NAME.NEEDS_REVIEW"


def test_the_first_letter_route_does_not_rescue_a_different_name() -> None:
    res = _verdict("Zebra", "Cobra")
    assert res.outcome is Outcome.FAIL
    assert res.reason_code == "BRAND.NAME.MISMATCH"


# ---------------------------------------------------------------------------
# Shapes and registration
# ---------------------------------------------------------------------------


def test_the_reader_payload_shape_is_read() -> None:
    """The extractor returns {brand_name, confidence}, not a bare string."""
    res = _verdict({"brand_name": "Stone's Throw", "confidence": 0.95}, "Stone's Throw")
    assert res.outcome is Outcome.PASS


def test_no_declared_brand_means_the_check_does_not_apply() -> None:
    res = _verdict("Stone's Throw", None)
    assert res.outcome is Outcome.NOT_APPLICABLE
    assert res.reason_code is None


def test_validator_registered() -> None:
    assert "fuzzy_brand" in VALIDATOR_REGISTRY
