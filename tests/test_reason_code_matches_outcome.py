"""Every finding's reason code says what its outcome says.

`rules/reason_codes.yaml` gives each code a severity: a `reject` code says what
a label got wrong, and a `warn` code says what the product could not settle.
The verdict a reviewer reads is set by the finding, not by the registry, so
nothing held the two together: a mismatch could arrive carrying a code whose
words say the product could not decide, and a review could arrive carrying no
code at all, which tells the reviewer nothing about what to look at. The
second happened on 76 checks until `docs/decisions.md#0055`.

`code_outcome_faults` is the check. It runs over the corpus here, and
`eval/corpus_check.py` prints what it finds on either label set.
"""

from __future__ import annotations

from eval.corpus_check import LabelOutcome, RuleOutcome, code_outcome_faults, registry_severities
from tests.test_corpus_outcomes import _outcomes

_SEVERITIES = {"X.Y.REJECTED": "reject", "X.Y.UNSETTLED": "warn"}


def _label(**rules: tuple[str, str]) -> list[LabelOutcome]:
    return [LabelOutcome("L", "needs_review", {k: RuleOutcome(*v) for k, v in rules.items()})]


def test_no_corpus_finding_carries_a_code_that_contradicts_its_outcome() -> None:
    faults = code_outcome_faults(list(_outcomes()), registry_severities())
    assert not faults, "\n".join(faults)


def test_findings_that_agree_with_their_codes_pass() -> None:
    outcomes = _label(
        a=("fail", "X.Y.REJECTED"), b=("needs_review", "X.Y.UNSETTLED"), c=("pass", "")
    )
    assert code_outcome_faults(outcomes, _SEVERITIES) == []


def test_a_review_with_no_code_is_caught() -> None:
    assert code_outcome_faults(_label(a=("needs_review", "")), _SEVERITIES) == [
        "L a: needs_review with no reason code"
    ]


def test_a_mismatch_with_a_review_code_is_caught() -> None:
    assert code_outcome_faults(_label(a=("fail", "X.Y.UNSETTLED")), _SEVERITIES) == [
        "L a: fail with X.Y.UNSETTLED, a warn code"
    ]


def test_a_review_with_a_rejection_code_is_caught() -> None:
    assert code_outcome_faults(_label(a=("needs_review", "X.Y.REJECTED")), _SEVERITIES) == [
        "L a: needs_review with X.Y.REJECTED, a reject code"
    ]


def test_an_unregistered_code_is_caught() -> None:
    assert code_outcome_faults(_label(a=("fail", "X.Y.UNKNOWN")), _SEVERITIES) == [
        "L a: fail with X.Y.UNKNOWN, a code the registry has not got"
    ]
