import { describe, expect, it } from "vitest";
import { decidingFinding } from "./decidingFinding";
import type { FieldFindingWire, RuleFindingWire } from "../types/envelopes";

function finding(
  rule_id: string,
  disposition: RuleFindingWire["disposition"],
  plain_language_explanation = "",
): RuleFindingWire {
  return {
    rule_id,
    cfr_citation: "27 CFR §7.65",
    disposition,
    reason_code: "",
    plain_language_explanation,
    matched_value: "",
  };
}

function field(...rule_findings: RuleFindingWire[]): FieldFindingWire {
  return {
    field_name: "alcohol_content",
    extracted_value: "ALC. 20.3%",
    expected_value: "ALC. 20.3% BY VOL.",
    evidence: { bbox: [0, 0, 0, 0], crop_ref: "", extraction_confidence: 0.9, face_tag: "front" },
    rule_findings,
    ai_suggestion: { present: false },
    field_confidence: { band: "high", numeric: 0.9 },
  } as FieldFindingWire;
}

describe("decidingFinding", () => {
  it("shows the rule that set the pill, not the first one evaluated", () => {
    // The order the Bruery's malt alcohol statement arrives in.
    const chosen = decidingFinding(
      field(
        finding("malt.alcohol.conditional_required", "pass"),
        finding("malt.alcohol.format", "needs_review", "The statement is not in the required form."),
        finding("malt.alcohol.matches_application", "pass", "The label states 20.3 and the application 20.3."),
      ),
    );
    expect(chosen?.rule_id).toBe("malt.alcohol.format");
  });

  it("prefers a rule that explains itself over one that does not", () => {
    const chosen = decidingFinding(
      field(
        finding("malt.class_type.present", "pass"),
        finding(
          "malt.class_type.matches_application",
          "pass",
          'The label designates "BARREL-AGED IMPERIAL STOUT", which carries "STOUT" inside it.',
        ),
      ),
    );
    expect(chosen?.rule_id).toBe("malt.class_type.matches_application");
  });

  it("takes a failure ahead of anything else", () => {
    const chosen = decidingFinding(
      field(
        finding("common.warning.present", "pass", "The warning is on the label."),
        finding("common.warning.verbatim", "fail", "One word differs from the regulation."),
      ),
    );
    expect(chosen?.rule_id).toBe("common.warning.verbatim");
  });

  it("has nothing to show when no rule ran", () => {
    expect(decidingFinding(field())).toBeNull();
  });
});
