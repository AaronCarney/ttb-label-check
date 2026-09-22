"""fuzzy_brand routes one label brand mark against every name the application
says the label may carry.

The admissible set is the declared brand, the fanciful name, and any trade
name the application marks "(Used on label)". Four routes run in order —
exact, whole words, score, and the review-only first-letter route — and the
result names which admissible value matched, so a reviewer looking at a label
whose mark is not the brand field's wording is told where that name came from.
A mark none of them settles goes to a reviewer, never to a mismatch: the mark
is the reader's guess at which line is the brand (docs/decisions.md#0052).
Searching the label's other lines is tested in test_brand_search.py.

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
from tests.rules.fixtures import make_context, make_evidence, make_expected, make_obs, make_rule

PASS_THRESHOLD = 0.92
NEEDS_REVIEW_THRESHOLD = 0.85


def _rule():
    return make_rule(
        rule_id="brand.match",
        cfr_citation="27 CFR §4.33",
        validator="fuzzy_brand",
        reason_code="BRAND.IDENTIFY.UNCERTAIN",
        severity=Severity.WARN,
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
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"


def test_a_trade_name_repeating_the_brand_leaves_the_finding_on_the_brand() -> None:
    """An applicant whose trade name repeats its brand is common. When both
    score the same, the finding names the brand the application declares, not
    the trade name, because that is the ordinary case. The trade name sorts
    after the brand, so a tie settled by comparing the names would pick it."""
    res = _verdict("Acmee Spirits", "ACME SPIRITS", trade_names_used_on_label=("Acme Spirits",))
    assert res.outcome is Outcome.PASS
    assert res.message and "the brand the application declares" in res.message, res.message


def test_a_blank_name_in_the_application_matches_nothing() -> None:
    """The reader placed a brand box and read no text from it, so the check runs
    on an empty reading. A blank fanciful name or trade name must not be the
    empty string that reading equals."""
    obs = make_obs(
        field_id="brand",
        value="",
        extra_evidence=(make_evidence(field_id="brand", bbox=(1, 2, 3, 4)),),
    )
    exp = make_expected(
        field_id="brand",
        value="Acme",
        parameters={"fanciful_name": "  ", "trade_names_used_on_label": (" ",)},
    )
    res = fuzzy_brand(obs, exp, _rule(), make_context())
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"


# ---------------------------------------------------------------------------
# Scores and thresholds
# ---------------------------------------------------------------------------


def test_a_near_spelling_above_the_threshold_matches() -> None:
    # One letter misread; a punctuation-only pair would take the route above.
    res = _verdict("Stones Thraw Bourbon", "Stones Throw Bourbon")
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


def test_a_different_name_below_the_floor_goes_to_a_reviewer() -> None:
    """The mark is not the declared name, and nothing else read shows it. That
    is a reviewer's question and never a mismatch: the mark is a guess at which
    line is the brand. The finding shows the mark the reader took."""
    res = _verdict("Acme", "Bizmark")
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.severity is Severity.WARN
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"
    assert res.message and '"Acme"' in res.message and '"Bizmark"' in res.message


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
    assert res.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert res.reason_code == "BRAND.IDENTIFY.UNCERTAIN"


# ---------------------------------------------------------------------------
# A difference of punctuation or spacing alone
# ---------------------------------------------------------------------------
#
# Scored, a punctuation difference depends on how long the name is: "Stones
# Throw" against "Stone's Throw" scores 0.9846 and passes, "Os" against "O's"
# scores 0.6111 and is rejected. The same dropped apostrophe cannot be a match
# in one brand and a different name in another, so this is decided by what
# differs, not by a score, and the finding says what differs.


@pytest.mark.parametrize(
    ("label", "declared"),
    [
        ("O'S", "Os"),  # a mismatch by score
        ("D.O.M.", "DOM"),  # needs review by score
        ("AL'S", "Als"),  # a match by score, and now by what differs
        ("Stones Throw", "Stone's Throw"),
        ("FIRESTONE", "Fire Stone"),
    ],
)
def test_a_difference_only_of_punctuation_or_spacing_is_a_match_that_says_so(
    label, declared
) -> None:
    res = _verdict(label, declared)
    assert res.outcome is Outcome.PASS
    assert res.message == (
        f'The label shows "{label}" against the brand the application declares, '
        f'"{declared}". They differ only in punctuation or spacing, which TTB\'s '
        "allowable revisions let a label change without a new approval."
    )


def test_the_punctuation_route_names_the_admissible_value_it_matched() -> None:
    res = _verdict("O'S", "Harbor Spirits", fanciful_name="Os")
    assert res.outcome is Outcome.PASS
    assert res.matched_value == "Os"
    assert "the fanciful name the application declares" in (res.message or "")


def test_a_symbol_that_stands_for_a_word_is_not_punctuation() -> None:
    res = _verdict("A&W", "AW")
    assert "differ only in punctuation" not in (res.message or "")


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
