/** Whether a check finished, and what stopped it if it did not.
 *
 *  The audit trail is the only place an engine failure is recorded — a failure
 *  happens before or instead of a rule, so it has no field to hang off. Every
 *  engine-failure row carries an `evidence_ref` beginning `engine_failure/`,
 *  written by `app/services/evaluator.py` and `build_short_circuit_envelope`
 *  in `app/services/envelope_builder.py`; rule outcomes use `vr/` and
 *  `reason_code/`, and the rule-pack rows use `rule_pack/`. That prefix is
 *  what tells them apart here. Drift guard:
 *  `tests/test_engine_failure_evidence_ref.py`.
 *
 *  Reading `per_rule_trace[0]` instead, as BatchItemDetail once did, found the
 *  rule-pack row: it is written before anything can go wrong, so it is first on
 *  every trace. A reviewer whose label was stopped by the evaluation guard was
 *  told the batch had recorded `ENGINE.RULE_PACK.SELECTED` against it.
 */
import type { PerRuleTraceEntry } from "../types/envelopes";

const _ENGINE_FAILURE_PREFIX = "engine_failure/";

/** The whole-evaluation guard stopping a check that ran too long. */
export const SLA_TIMEOUT_CODE = "ENGINE.SLA.TIMEOUT";

/** The reason code of the first engine failure on this trace, or null if the
 *  evaluation hit none. The first, not the last: where an evaluation hit more
 *  than one, the earliest is the one that explains the rest. */
export function engineFailureCode(trace: PerRuleTraceEntry[]): string | null {
  return (
    trace.find((e) => e.evidence_ref.startsWith(_ENGINE_FAILURE_PREFIX))?.rule_id ?? null
  );
}

/** Whether the evaluation guard stopped this check before it finished.
 *
 *  A check stopped this way returns what it had completed rather than nothing,
 *  so its results can look whole. They are not, and the reviewer has to be
 *  told: any rule that had not run yet reported no finding, which is not the
 *  same as finding nothing wrong. */
export function wasStoppedEarly(trace: PerRuleTraceEntry[]): boolean {
  return trace.some((e) => e.rule_id === SLA_TIMEOUT_CODE);
}
