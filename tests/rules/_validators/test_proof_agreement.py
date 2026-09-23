"""proof_agreement: a proof the label states must be twice the label's ABV.

27 CFR §5.1 defines proof as twice the percentage of alcohol by volume, and
§5.65(b)(1)(i) lets a spirits label state it beside the alcohol content. The
comparison is inside the label — its proof against its own ABV — so the
application's figure never decides it.

Only a proof printed on the ABV statement's line, or the line next to it, can
reject. A number elsewhere on the label that reads as a proof may be something
the reader could not tell apart from one, so a disagreement there goes to a
reviewer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.rules._validators.proof_agreement import proof_agreement
from app.schemas.rejection import Outcome, Severity
from tests.rules.fixtures import make_context, make_expected, make_obs, make_rule

_REVIEW = "ALCOHOL_CONTENT.PROOF.NEEDS_REVIEW"
_DISAGREES = "ALCOHOL_CONTENT.PROOF.DISAGREES"


def _rule():
    return make_rule(
        rule_id="spirits.alcohol.proof_agrees",
        cfr_citation="27 CFR §5.65(b)(1)(i), §5.1",
        validator="proof_agreement",
        reason_code=_DISAGREES,
        parameters={
            "needs_review_reason_code": _REVIEW,
            "disagreement_reason_code": _DISAGREES,
        },
        evidence_required=("abv",),
    )


def _proof(value: str, *, beside: bool = True, confidence: float = 0.95) -> dict[str, Any]:
    return {
        "value": value,
        "text": f"{value} PROOF",
        "confidence": confidence,
        "beside_abv": beside,
    }


def _check(abv: float | None, *proofs: dict[str, Any], declared: str | None = None, **payload):
    value: dict[str, Any] = {
        "abv_pct": abv,
        "unit": "%" if abv is not None else "",
        "alc_text": "" if abv is None else f"{abv:g}% ALC/VOL",
        "confidence": 0.95,
        "proof": list(proofs),
    }
    value.update(payload)
    obs = make_obs(field_id="abv", value=value)
    exp = make_expected(
        field_id="abv",
        value=declared,
        abv_labeled_pct=Decimal(declared) if declared else None,
    )
    return proof_agreement(obs, exp, _rule(), make_context())


def test_a_proof_twice_the_abv_matches() -> None:
    result = _check(45.0, _proof("90"))
    assert result.outcome is Outcome.PASS


def test_a_proof_that_is_not_twice_the_abv_beside_it_is_a_mismatch() -> None:
    result = _check(45.0, _proof("80"))
    assert result.outcome is Outcome.FAIL
    assert result.severity is Severity.REJECT
    assert result.reason_code == _DISAGREES
    assert result.message == "The label states 80 proof beside 45%; twice 45 is 90."


def test_a_proof_one_whole_unit_off_is_a_mismatch_not_a_rounding() -> None:
    result = _check(45.0, _proof("91"))
    assert result.outcome is Outcome.FAIL


def test_a_decimal_proof_equal_to_twice_a_decimal_abv_matches() -> None:
    # ttb-26218001000369: "Alc. 42.8% by vol." over "85.6 US PROOF".
    result = _check(42.8, _proof("85.6"))
    assert result.outcome is Outcome.PASS


@pytest.mark.parametrize(
    ("abv", "read"),
    [
        (58.5, "17"),  # ttb-23335001000512: "(117 Proof)" read as "(17 Proof)"
        (45.0, "910"),
        (5.5, "111"),
    ],
)
def test_a_proof_off_by_one_thin_one_goes_to_a_reviewer(abv: float, read: str) -> None:
    """A "1" is the figure the reader drops or adds, as it drops and adds thin
    letters inside a word, so a proof that is twice the ABV but for one of them
    is not shown to disagree."""
    result = _check(abv, _proof(read))
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _REVIEW
    assert result.message is not None and "misread" in result.message


def test_a_proof_rounded_to_its_printed_precision_goes_to_a_reviewer() -> None:
    # Twice 42.8 is 85.6; a label printing "86" has rounded it, which the
    # regulation neither permits nor forbids in words.
    result = _check(42.8, _proof("86"))
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.severity is Severity.WARN
    assert result.reason_code == _REVIEW


def test_one_wrong_proof_beside_the_abv_among_right_ones_is_a_mismatch() -> None:
    result = _check(45.0, _proof("90"), _proof("80"))
    assert result.outcome is Outcome.FAIL


def test_a_disagreeing_proof_away_from_the_abv_goes_to_a_reviewer() -> None:
    result = _check(45.0, _proof("80", beside=False))
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _REVIEW


def test_no_proof_on_the_label_means_the_check_does_not_apply() -> None:
    result = _check(45.0)
    assert result.outcome is Outcome.NOT_APPLICABLE


def test_an_unread_abv_with_a_proof_goes_to_a_reviewer_whatever_the_application_says() -> None:
    result = _check(None, _proof("80"), declared="45")
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _REVIEW
    assert "80" in (result.message or "")
    assert "45" in (result.message or "")


def test_a_figure_above_two_hundred_is_unreadable_and_goes_to_a_reviewer() -> None:
    result = _check(43.0, _proof("860"))
    assert result.outcome is Outcome.INSUFFICIENT_EVIDENCE
    assert result.reason_code == _REVIEW


def test_the_result_is_as_confident_as_its_least_confident_proof() -> None:
    # The engine's confidence floor reads this and sends a verdict resting on
    # a poor reading to a reviewer.
    result = _check(45.0, _proof("90"), _proof("80", confidence=0.3))
    assert result.aggregated_confidence == pytest.approx(0.3)


def test_a_reading_with_no_proof_list_is_read_from_its_alcohol_statement() -> None:
    # The cloud reader returns the statement as printed and no proof list, and
    # gets the same deterministic check.
    obs = make_obs(
        field_id="abv",
        value={
            "abv_pct": 45.0,
            "unit": "%",
            "alc_text": "45% Alc./Vol. (80 Proof)",
            "confidence": 0.9,
        },
        confidence=0.9,
    )
    result = proof_agreement(obs, make_expected(field_id="abv"), _rule(), make_context())
    assert result.outcome is Outcome.FAIL
    assert result.aggregated_confidence == pytest.approx(0.9)


def test_a_reading_with_no_proof_list_and_no_proof_in_its_statement_does_not_apply() -> None:
    obs = make_obs(
        field_id="abv",
        value={"abv_pct": 45.0, "unit": "%", "alc_text": "45% ALC/VOL", "confidence": 0.9},
    )
    result = proof_agreement(obs, make_expected(field_id="abv"), _rule(), make_context())
    assert result.outcome is Outcome.NOT_APPLICABLE
