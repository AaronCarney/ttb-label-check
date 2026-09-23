import { describe, it, expect, vi } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { FieldCard } from "./FieldCard";
import type { FieldFindingWire, RuleFindingWire } from "../types/envelopes";

const _stub: FieldFindingWire = {
  field_name: "brand_name",
  extracted_value: "Stone's Throw",
  expected_value: "Stone's Throw",
  evidence: { bbox: [0, 0, 100, 50], crop_ref: "x", extraction_confidence: 0.9, face_tag: "front" },
  rule_findings: [
    {
      rule_id: "common.brand.exact_or_normalized",
      cfr_citation: "27 CFR §5.64",
      disposition: "pass",
      reason_code: "BRAND.NAME.MATCH",
      plain_language_explanation: "OK",
      matched_value: "",
      lean: "pass",
    },
  ],
  ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
  field_confidence: { band: "high", numeric: 0.94 },
  lean: "pass",
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

  // A label is filed as several photographs and its mandatory elements are
  // spread across them. A reviewer told a warning is missing has to know which
  // picture was searched, and the photographs sit above this card, not in it.
  it("names the photograph the value was read from", () => {
    const back = { ..._stub, evidence: { ..._stub.evidence, face_tag: "back" } };
    const { getByText } = renderWithProviders(<FieldCard field={back} />);
    expect(getByText("Read from")).toBeInTheDocument();
    expect(getByText("Back")).toBeInTheDocument();
  });

  it("says nothing about the face when the reading did not record one", () => {
    const unknown = { ..._stub, evidence: { ..._stub.evidence, face_tag: "" } };
    const { queryByText } = renderWithProviders(<FieldCard field={unknown} />);
    expect(queryByText("Read from")).not.toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<FieldCard field={_stub} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

// A result stands until the reviewer says it is wrong. The card asks nothing
// of them when it is right, offers the correction on every checked field, and
// never makes the choice for them (docs/decisions.md#0064).
describe("correcting a field's result", () => {
  const _failing: FieldFindingWire = {
    ..._stub,
    rule_findings: [{ ..._stub.rule_findings[0]!, disposition: "fail" }],
  };

  it("offers no correction where the page has nowhere to send one", () => {
    const { queryByRole } = renderWithProviders(<FieldCard field={_stub} />);
    expect(queryByRole("button", { name: "This result is wrong" })).toBeNull();
  });

  it("offers the other two results, none of them chosen, only once asked", () => {
    const { getByRole, queryByRole } = renderWithProviders(
      <FieldCard field={_failing} onCorrect={async () => true} />,
    );
    expect(queryByRole("group", { name: /Correct the result/ })).toBeNull();
    const open = getByRole("button", { name: "This result is wrong" });
    expect(open.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(open);
    expect(open.getAttribute("aria-expanded")).toBe("true");
    const group = getByRole("group", { name: "Correct the result for Brand name" });
    const choices = within(group)
      .getAllByRole("button")
      .map((b) => b.textContent);
    expect(choices).toEqual(["Pass", "Needs review", "Cancel"]);
  });

  it("sends the chosen result and closes once it is saved", async () => {
    const onCorrect = vi.fn(async () => true);
    const { getByRole, queryByRole } = renderWithProviders(
      <FieldCard field={_failing} onCorrect={onCorrect} />,
    );
    fireEvent.click(getByRole("button", { name: "This result is wrong" }));
    fireEvent.click(getByRole("button", { name: "Pass" }));
    await waitFor(() => expect(queryByRole("group", { name: /Correct the result/ })).toBeNull());
    expect(onCorrect).toHaveBeenCalledWith("pass");
  });

  it("stays open when the correction was not saved", async () => {
    const onCorrect = vi.fn(async () => false);
    const { getByRole } = renderWithProviders(<FieldCard field={_failing} onCorrect={onCorrect} />);
    fireEvent.click(getByRole("button", { name: "This result is wrong" }));
    fireEvent.click(getByRole("button", { name: "Pass" }));
    await waitFor(() => expect(onCorrect).toHaveBeenCalled());
    expect(getByRole("group", { name: /Correct the result/ })).toBeInTheDocument();
  });

  it("shows the reviewer's result, and what the check had said", () => {
    const correction = {
      field_name: "brand_name",
      original_disposition: "fail" as const,
      applied_disposition: "pass" as const,
      reason_code: "REVIEWER.CORRECTION.PASS",
      justification_text: null,
      reviewer_id: "session-a",
      timestamp: "2026-09-22T00:00:00Z",
    };
    const { getByRole, getByText } = renderWithProviders(
      <FieldCard field={_failing} correction={correction} onCorrect={async () => true} />,
    );
    expect(getByRole("status", { name: "Disposition: Pass" })).toBeInTheDocument();
    expect(getByText("Corrected by the reviewer. The check reported Fail.")).toBeInTheDocument();
  });

  it("has no axe violations with the choices open", async () => {
    const { container, getByRole } = renderWithProviders(
      <FieldCard field={_failing} onCorrect={async () => true} />,
    );
    fireEvent.click(getByRole("button", { name: "This result is wrong" }));
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("a field the check could not settle", () => {
  const _unsure: FieldFindingWire = {
    ..._stub,
    rule_findings: [{ ...(_stub.rule_findings[0] as RuleFindingWire), disposition: "needs_review", lean: "pass" }],
    lean: "pass",
  };

  it("shows its best guess, flagged for review, with a Confirm button", () => {
    const { getByRole, getByText } = renderWithProviders(
      <FieldCard field={_unsure} onCorrect={async () => true} onConfirm={async () => true} />,
    );
    expect(getByRole("status", { name: "Disposition: Pass" })).toBeInTheDocument();
    expect(getByText("Needs review")).toBeInTheDocument();
    expect(getByRole("button", { name: "Confirm Pass" })).toBeInTheDocument();
  });

  it("confirms the guess it shows", async () => {
    const onConfirm = vi.fn(async () => true);
    const { getByRole } = renderWithProviders(<FieldCard field={_unsure} onConfirm={onConfirm} />);
    fireEvent.click(getByRole("button", { name: "Confirm Pass" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith("pass"));
  });

  it("offers the answer it does not show as the correction", () => {
    const { getByRole } = renderWithProviders(
      <FieldCard field={_unsure} onCorrect={async () => true} onConfirm={async () => true} />,
    );
    fireEvent.click(getByRole("button", { name: "This result is wrong" }));
    const group = getByRole("group", { name: "Correct the result for Brand name" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["Fail", "Cancel"]);
  });

  it("asks nothing more once confirmed", () => {
    const confirmation = {
      field_name: "brand_name",
      original_disposition: "needs_review" as const,
      applied_disposition: "pass" as const,
      reason_code: "REVIEWER.CONFIRMATION.PASS",
      justification_text: null,
      reviewer_id: "session-a",
      timestamp: "2026-09-22T00:00:00Z",
    };
    const { getByText, queryByRole, queryByText } = renderWithProviders(
      <FieldCard field={_unsure} correction={confirmation} onConfirm={async () => true} />,
    );
    expect(getByText("Confirmed by the reviewer.")).toBeInTheDocument();
    expect(queryByText("Needs review")).toBeNull();
    expect(queryByRole("button", { name: /Confirm/ })).toBeNull();
  });

  it("has no Confirm button on a settled result", () => {
    const { queryByRole } = renderWithProviders(<FieldCard field={_stub} onConfirm={async () => true} />);
    expect(queryByRole("button", { name: /Confirm/ })).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <FieldCard field={_unsure} onCorrect={async () => true} onConfirm={async () => true} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
