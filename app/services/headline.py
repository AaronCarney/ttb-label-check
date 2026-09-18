"""The one reason code a result is summed up by, for a log line or an advisory."""

from __future__ import annotations

from app.schemas.wire.disposition import DispositionEnvelope


def headline_reason_code(envelope: DispositionEnvelope) -> str | None:
    """The one reason code that says why a label came out the way it did.

    None for a pass. Otherwise the first finding that did not pass; and for an
    envelope with no findings to name, the engine failure recorded on the
    trace. That row is found by its `engine_failure/` evidence ref, not taken
    from the top of the trace: the first row is the rule-pack selection, and
    naming it would say a timed-out check was about which rules applied.
    """
    if envelope.disposition == "pass":
        return None
    for field in envelope.fields:
        for finding in field.rule_findings:
            if finding.disposition in ("fail", "needs_review"):
                return finding.reason_code
    trace = envelope.audit_trail.per_rule_trace
    for entry in trace:
        if entry.evidence_ref.startswith("engine_failure/"):
            return entry.rule_id
    if trace:
        return trace[0].rule_id
    return None
