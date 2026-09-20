import type { FieldFindingWire, RuleFindingWire } from "../types/envelopes";

// A field runs several rules and the card has room for one verdict. Taking the
// first one in the list showed whichever rule happened to be evaluated first,
// which on a malt alcohol statement is `conditional_required` — a rule that
// checks the element is required at all, says nothing, and passes. The card
// then carried an empty verdict under a "Needs review" pill set by a different
// rule, with the sentence explaining the match hidden behind it.
//
// The rule worth showing is the one that decided the field: the same
// precedence the pill uses. Where several share that disposition, the one that
// has something to say wins, because a rule with no explanation tells a
// reviewer nothing they cannot already see.
const PRECEDENCE = ["fail", "needs_review", "pass"] as const;

export function decidingFinding(field: FieldFindingWire): RuleFindingWire | null {
  for (const disposition of PRECEDENCE) {
    const matching = field.rule_findings.filter((r) => r.disposition === disposition);
    if (matching.length === 0) continue;
    return matching.find((r) => r.plain_language_explanation) ?? matching[0] ?? null;
  }
  return null;
}
