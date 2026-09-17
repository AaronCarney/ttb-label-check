"""Pure disposition rule: the overall result for one submission."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from app.schemas.rejection import Outcome, Severity, ValidationResult

Disposition = Literal["pass", "fail", "needs_review"]

# One finding on its own reads as one of four things. A rule that did not
# apply is not a pass, and the reviewer is told so rather than shown a check
# that only ever had one side.
RuleDisposition = Literal["pass", "fail", "needs_review", "not_applicable"]

_PASS_LIKE = {Outcome.PASS, Outcome.NOT_APPLICABLE}


def _rejects(result: ValidationResult) -> bool:
    """Does this finding reject the label, or is it a reviewer's to settle?

    A rule marked `warn` in the rule pack is one whose disagreement is not
    evidence the label is wrong — the applicant's name and address block
    carries names the label need not print, so a name it omits is a question,
    not a rejection. Treating every difference as a rejection would throw that
    distinction away and reject most real labels.
    """
    return result.outcome == Outcome.FAIL and result.severity != Severity.WARN


def rule_disposition(result: ValidationResult) -> RuleDisposition:
    """What one finding says, in the words a reviewer is shown.

    This is the only place an outcome becomes a verdict. Every surface that
    shows a per-rule verdict — the audit trail, the reviewer's field card, the
    overall result below — calls this one function, because a reviewer who
    reads *fail* on a field and *needs_review* on the same rule in the audit
    trail cannot tell which is the product's answer.

    A check the label's reading was too poor to settle says so:
    `INSUFFICIENT_EVIDENCE` is neither a pass nor a rejection, so it lands in
    `needs_review`, and so do a timed-out and an errored rule.
    """
    if result.outcome == Outcome.PASS:
        return "pass"
    if result.outcome == Outcome.NOT_APPLICABLE:
        return "not_applicable"
    if _rejects(result):
        return "fail"
    return "needs_review"


def compute_disposition(results: Iterable[ValidationResult]) -> Disposition:
    """fail iff any FAIL the rule pack lets reject; pass iff every PASS or
    NOT_APPLICABLE; else needs_review.
    Empty results → needs_review (engine produced nothing — honest failure)."""
    results = tuple(results)
    if not results:
        return "needs_review"
    if any(_rejects(r) for r in results):
        return "fail"
    if all(r.outcome in _PASS_LIKE for r in results):
        return "pass"
    return "needs_review"
