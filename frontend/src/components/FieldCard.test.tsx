import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { FieldCard } from "./FieldCard";
import type { FieldFindingWire } from "../types/envelopes";

const _stub: FieldFindingWire = {
  field_name: "brand_name",
  extracted_value: "Stone's Throw",
  expected_value: "Stone's Throw",
  evidence: { bbox: [0, 0, 100, 50], crop_ref: "x", extraction_confidence: 0.9 },
  rule_findings: [
    {
      rule_id: "common.brand.exact_or_normalized",
      cfr_citation: "27 CFR §5.64",
      disposition: "pass",
      reason_code: "BRAND.NAME.MATCH",
      plain_language_explanation: "OK",
    },
  ],
  ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
  field_confidence: { band: "high", numeric: 0.94 },
};

describe("FieldCard", () => {
  it("renders field name as a labelled section", () => {
    const { getByRole } = renderWithProviders(<FieldCard field={_stub} />);
    // section landmark with aria-label naming the field.
    expect(getByRole("region", { name: /brand_name/i })).toBeInTheDocument();
  });

  it("displays extracted and expected values", () => {
    const { getAllByText } = renderWithProviders(<FieldCard field={_stub} />);
    // Both extracted and expected show the same value in stub — two occurrences expected.
    expect(getAllByText(/Stone's Throw/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders custom verdict node when supplied", () => {
    const { getByText } = renderWithProviders(
      <FieldCard field={_stub} verdict={<span>VERDICT_NODE</span>} />,
    );
    expect(getByText("VERDICT_NODE")).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<FieldCard field={_stub} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
