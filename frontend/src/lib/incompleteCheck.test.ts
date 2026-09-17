import { describe, it, expect } from "vitest";
import { engineFailureCode, wasStoppedEarly } from "./incompleteCheck";
import type { PerRuleTraceEntry } from "../types/envelopes";

const _entry = (
  rule_id: string,
  evidence_ref: string,
): PerRuleTraceEntry => ({ rule_id, disposition: "needs_review", evidence_ref });

// The trace an evaluation stopped by the guard actually produces, read off the
// live service on 2026-09-17. The rule-pack row is written first, before
// anything can go wrong, so it is always ahead of the failure.
const _timedOut: PerRuleTraceEntry[] = [
  _entry("ENGINE.RULE_PACK.SELECTED", "rule_pack/spirits"),
  _entry("ENGINE.SLA.TIMEOUT", "engine_failure/TimeoutError"),
];

describe("engineFailureCode", () => {
  it("finds the failure rather than whatever row happens to be first", () => {
    // Reading per_rule_trace[0] told the reviewer that rule-pack selection was
    // what the batch recorded against their label.
    expect(engineFailureCode(_timedOut)).toBe("ENGINE.SLA.TIMEOUT");
  });

  it("names the first failure when an evaluation hit more than one", () => {
    const both = [
      _entry("ENGINE.RULE_PACK.SELECTED", "rule_pack/spirits"),
      _entry("ENGINE.EXTRACTION.UNAVAILABLE", "engine_failure/RuntimeError"),
      _entry("ENGINE.SLA.TIMEOUT", "engine_failure/TimeoutError"),
    ];
    expect(engineFailureCode(both)).toBe("ENGINE.EXTRACTION.UNAVAILABLE");
  });

  it("reports none when nothing failed", () => {
    expect(engineFailureCode([_entry("R-BRAND-01", "vr/R-BRAND-01")])).toBeNull();
    expect(engineFailureCode([])).toBeNull();
  });
});

describe("wasStoppedEarly", () => {
  it("recognises an evaluation the guard stopped", () => {
    expect(wasStoppedEarly(_timedOut)).toBe(true);
  });

  it("does not flag an evaluation that finished", () => {
    expect(wasStoppedEarly([_entry("R-BRAND-01", "vr/R-BRAND-01")])).toBe(false);
  });
});
