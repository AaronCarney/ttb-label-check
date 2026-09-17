"""Honest failure: a check the engine could not settle never reports a match."""

import pytest

from app.schemas.expected import BeverageClass
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.disposition import compute_disposition


def _em():
    return EngineMeta(
        engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0
    )


def _vr(outcome):
    return ValidationResult(
        rule_id="R",
        cfr_citation="27 CFR §x",
        beverage_class=BeverageClass.SPIRITS,
        outcome=outcome,
        severity=Severity.INFO,
        aggregated_confidence=0.9,
        engine_meta=_em(),
    )


@pytest.mark.parametrize(
    "outcomes, expected",
    [
        ((Outcome.PASS, Outcome.PASS), "pass"),
        ((Outcome.PASS, Outcome.NOT_APPLICABLE), "pass"),
        ((Outcome.PASS, Outcome.FAIL), "fail"),
        ((Outcome.FAIL, Outcome.NOT_APPLICABLE), "fail"),
        ((Outcome.PASS, Outcome.INSUFFICIENT_EVIDENCE), "needs_review"),
        ((Outcome.PASS, Outcome.TIMEOUT), "needs_review"),
        ((Outcome.PASS, Outcome.ERROR), "needs_review"),
        ((Outcome.FAIL, Outcome.TIMEOUT), "fail"),  # fail wins
    ],
)
def test_disposition_rule(outcomes, expected):
    assert compute_disposition(tuple(_vr(o) for o in outcomes)) == expected


def test_empty_results_route_to_needs_review():
    assert compute_disposition(()) == "needs_review"


# ---------------------------------------------------------------------------
# A finding the rule pack marks warn is a reviewer's, not a rejection
# ---------------------------------------------------------------------------


def _warn_fail():
    """A rule that found a difference and is not entitled to reject over it.

    Several comparisons are written this way on purpose: the applicant's name
    and address block, for instance, carries names the label need not print,
    so a name it does not carry is not evidence the label is wrong.
    """
    return ValidationResult(
        rule_id="R-warn",
        cfr_citation="27 CFR §x",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.FAIL,
        severity=Severity.WARN,
        reason_code="X.MATCH.NEEDS_REVIEW",
        aggregated_confidence=0.9,
        engine_meta=_em(),
    )


def _reject_fail():
    return ValidationResult(
        rule_id="R-reject",
        cfr_citation="27 CFR §x",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.FAIL,
        severity=Severity.REJECT,
        reason_code="X.MATCH.DISAGREE",
        aggregated_confidence=0.9,
        engine_meta=_em(),
    )


def test_a_warn_finding_alone_goes_to_a_reviewer():
    assert compute_disposition((_vr(Outcome.PASS), _warn_fail())) == "needs_review"


def test_a_warn_finding_does_not_outrank_a_rejection():
    assert compute_disposition((_warn_fail(), _reject_fail())) == "fail"


def test_a_warn_finding_still_keeps_the_label_out_of_pass():
    assert compute_disposition((_warn_fail(),)) == "needs_review"
