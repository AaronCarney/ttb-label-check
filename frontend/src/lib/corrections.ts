import type { DispositionEnvelope, OverrideEntry } from "../types/envelopes";

export type Verdict = "pass" | "fail" | "needs_review";

/** What the override endpoint answers: the entry it recorded, and the label's
 * result once that entry is applied. The result is the server's to decide
 * (`app/services/disposition.py`), so the page shows it rather than working it
 * out a second time. */
export interface OverrideApplied {
  entry: OverrideEntry;
  labelDisposition?: Verdict;
}

function _sameEntry(a: OverrideEntry, b: OverrideEntry): boolean {
  return a.reviewer_id === b.reviewer_id && a.timestamp === b.timestamp;
}

/** The envelope with one more override on its audit trail and the label's
 * result the server reported for it. Applying the same entry twice changes
 * nothing, because the page hears of one correction twice: from its own
 * request, and from the batch stream while that is still open. */
export function withOverride(envelope: DispositionEnvelope, applied: OverrideApplied): DispositionEnvelope {
  const overrides = envelope.audit_trail.overrides;
  const known = overrides.some((o) => _sameEntry(o, applied.entry));
  return {
    ...envelope,
    disposition: applied.labelDisposition ?? envelope.disposition,
    audit_trail: known ? envelope.audit_trail : { ...envelope.audit_trail, overrides: [...overrides, applied.entry] },
  };
}

/** The reviewer's latest correction to one field, or null if they made none. */
export function fieldCorrection(envelope: DispositionEnvelope, fieldName: string): OverrideEntry | null {
  return [...envelope.audit_trail.overrides].reverse().find((o) => o.field_name === fieldName) ?? null;
}

/** The registered reason code a field correction carries, one per result the
 * reviewer can correct to (`rules/reason_codes.yaml`, REVIEWER bin). */
export const CORRECTION_CODES: Record<Verdict, string> = {
  pass: "REVIEWER.CORRECTION.PASS",
  fail: "REVIEWER.CORRECTION.FAIL",
  needs_review: "REVIEWER.CORRECTION.NEEDS_REVIEW",
};
