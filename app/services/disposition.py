"""Pure disposition rule: the overall result for one submission."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.wire.disposition import DispositionEnvelope

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


def field_disposition(envelope: DispositionEnvelope, field_name: str) -> Disposition | None:
    """What one field's card says now: the reviewer's latest correction to it,
    else the worst of its rule verdicts. None when the field is not on the
    label's result or no rule checked it, since a check that never ran has no
    result to correct."""
    field = next((f for f in envelope.fields if f.field_name == field_name), None)
    if field is None:
        return None
    for override in reversed(envelope.audit_trail.overrides):
        if override.field_name == field_name:
            return override.applied_disposition
    verdicts = {rf.disposition for rf in field.rule_findings}
    if not verdicts:
        return None
    if "fail" in verdicts:
        return "fail"
    if "needs_review" in verdicts:
        return "needs_review"
    return "pass"


def disposition_after_overrides(envelope: DispositionEnvelope) -> Disposition:
    """The label's result once a reviewer's corrections are applied.

    A result stands until someone says it is wrong, so with no correction this
    is the engine's own answer. A correction to one field replaces that field's
    rule verdicts with the reviewer's, and the label is then decided by the same
    rule as `compute_disposition`: one failed field fails the label, every field
    passing passes it, and anything else goes to a reviewer. The rows the check
    recorded that belong to no field — a stopped evaluation, a photo too poor to
    read — keep their say, so correcting every field of an unfinished check does
    not make it a pass.

    A correction to the whole label (`field_name` empty) counts as one more
    verdict beside the fields, and the latest one is the one that counts. It
    can hold a label back, but it cannot lift one: a label with a failed field
    fails whatever the whole-label correction said, because one element that
    does not match rejects the application. The latest correction to a field
    is that field's answer.
    """
    overrides = envelope.audit_trail.overrides
    whole_label = [o.applied_disposition for o in overrides if o.field_name is None]
    corrected = {o.field_name: o.applied_disposition for o in overrides if o.field_name is not None}
    if not corrected:
        from_fields: Disposition = envelope.disposition
    else:
        # The trace carries one row per rule, and one more per rule that named a
        # reason code (`evidence_ref` "reason_code/<rule_id>"). A corrected
        # field's rules leave through both.
        replaced = {
            rf.rule_id
            for f in envelope.fields
            if f.field_name in corrected
            for rf in f.rule_findings
        }
        from_fields = _combine(
            [
                *(
                    row.disposition
                    for row in envelope.audit_trail.per_rule_trace
                    if row.rule_id not in replaced
                    and row.evidence_ref.removeprefix("reason_code/") not in replaced
                ),
                *corrected.values(),
            ]
        )
    return _combine([from_fields, whole_label[-1]]) if whole_label else from_fields


def _combine(verdicts: Iterable[RuleDisposition]) -> Disposition:
    """`compute_disposition` over verdicts already read, as the trace holds them."""
    verdicts = tuple(verdicts)
    if not verdicts:
        return "needs_review"
    if "fail" in verdicts:
        return "fail"
    if all(v in ("pass", "not_applicable") for v in verdicts):
        return "pass"
    return "needs_review"


Lean = Literal["pass", "fail"]


def field_lean(envelope: DispositionEnvelope, field_name: str) -> Lean | None:
    """The answer one field's card shows pre-filled.

    The reviewer's latest word on the field, where it is a match or a
    mismatch. Otherwise the check's own lean (`FieldFindingWire.lean`), which
    a field sent back to review returns to. None when no rule checked the
    field, since a check that never ran has no answer.
    """
    field = next((f for f in envelope.fields if f.field_name == field_name), None)
    if field is None:
        return None
    latest = next(
        (o for o in reversed(envelope.audit_trail.overrides) if o.field_name == field_name), None
    )
    if latest is not None and latest.applied_disposition != "needs_review":
        return latest.applied_disposition
    return field.lean


def label_lean(envelope: DispositionEnvelope) -> Lean:
    """The answer the label shows pre-filled.

    A settled label is its own answer. A label still under review leans to a
    mismatch if any field does, or if a check that belongs to no field card
    went to review — a stopped evaluation, a photo too poor to read, a field
    the reader found nothing for — since nothing there points to a match.
    Otherwise it leans to a match.
    """
    if envelope.disposition != "needs_review":
        return envelope.disposition
    if any(field_lean(envelope, f.field_name) == "fail" for f in envelope.fields):
        return "fail"
    on_cards = {rf.rule_id for f in envelope.fields for rf in f.rule_findings}
    for row in envelope.audit_trail.per_rule_trace:
        if row.disposition != "needs_review":
            continue
        if row.rule_id in on_cards or row.evidence_ref.removeprefix("reason_code/") in on_cards:
            continue
        return "fail"
    return "pass"
