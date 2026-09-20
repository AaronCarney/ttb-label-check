import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { RuleVerdict } from "./RuleVerdict";
import type { RuleFindingWire } from "../types/envelopes";

const _rf: RuleFindingWire = {
  rule_id: "common.warning.heading_style",
  cfr_citation: "27 CFR §16.21(a)",
  disposition: "fail",
  reason_code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
  plain_language_explanation: "Heading not in bold caps.",
  matched_value: "",
};

describe("RuleVerdict", () => {
  it("renders inside its own labelled section, separate from any AI suggestion", () => {
    const { getByRole } = renderWithProviders(<RuleVerdict finding={_rf} />);
    expect(getByRole("region", { name: /Rule verdict/i })).toBeInTheDocument();
  });

  it("shows reason code, explanation, and disposition pill", () => {
    const { getByText, getByRole } = renderWithProviders(<RuleVerdict finding={_rf} />);
    expect(getByText(/WARNING\.STYLE\.HEADING_NOT_BOLD_CAPS/)).toBeInTheDocument();
    expect(getByText(/Heading not in bold caps/)).toBeInTheDocument();
    expect(getByRole("status", { name: /Fail/i })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<RuleVerdict finding={_rf} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
