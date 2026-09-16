"""Pure disposition rule: the overall result for one submission."""
from __future__ import annotations

from typing import Iterable, Literal

from app.schemas.rejection import Outcome, Severity, ValidationResult


Disposition = Literal["pass", "fail", "needs_review"]
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
