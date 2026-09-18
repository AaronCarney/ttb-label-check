import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { BatchItemDetail } from "./BatchItemDetail";
import type { BatchSSEEvent } from "../types/sse";
import type { FieldFindingWire } from "../types/envelopes";

const _field = (
  name: FieldFindingWire["field_name"],
  extracted: string,
  expected: string,
  finding: FieldFindingWire["rule_findings"],
): FieldFindingWire => ({
  field_name: name,
  extracted_value: extracted,
  expected_value: expected,
  evidence: { bbox: [0, 0, 1, 1], crop_ref: "c", extraction_confidence: 0.9, face_tag: "front" },
  rule_findings: finding,
  ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
  field_confidence: { band: "high", numeric: 0.9 },
});

const _row = (
  fields: FieldFindingWire[],
  trace: { rule_id: string; disposition: "needs_review"; evidence_ref: string }[] = [],
): BatchSSEEvent => ({
  batch_id: "B",
  queue_position: 0,
  evaluation_id: "ev-1",
  label_ref: "lbl-1",
  disposition: "fail",
  disposition_confidence: { band: "high", numeric: 0.92 },
  fields,
  audit_trail: {
    evaluation_id: "ev-1",
    rule_set_version: "0.1.0",
    model_version: null,
    prompt_version: null,
    input_hash: "x",
    output_hash: "y",
    started_at: "2026-09-16T00:00:00Z",
    completed_at: "2026-09-16T00:00:01Z",
    per_rule_trace: trace,
    overrides: [],
  },
  metrics: { total_duration_ms: 10, per_rule_durations_ms: [], vision_duration_ms: 5, cache_hit: false },
});

const _checked = _row([
  _field("brand_name", "Old Mill", "Olde Mill", [
    {
      rule_id: "R01",
      cfr_citation: "27 CFR 4.33",
      disposition: "fail",
      reason_code: "BRAND.NAME.MISMATCH",
      plain_language_explanation: "The brand on the label is not the brand on the application.",
    },
  ]),
  _field("net_contents", "750 ML", "750 ML", []),
]);

describe("BatchItemDetail", () => {
  it("prompts for a selection when no row is open", () => {
    const { getByText } = renderWithProviders(<BatchItemDetail row={null} />);
    expect(getByText(/Choose a label above/i)).toBeTruthy();
  });

  it("shows the opened label's fields, each with what was read and what was expected", () => {
    const { getByRole, getByText } = renderWithProviders(<BatchItemDetail row={_checked} />);
    expect(getByRole("region", { name: /Check results for lbl-1/i })).toBeTruthy();
    expect(getByRole("region", { name: "Field: brand_name" })).toBeTruthy();
    expect(getByRole("region", { name: "Field: net_contents" })).toBeTruthy();
    expect(getByText("Old Mill")).toBeTruthy();
    expect(getByText("Olde Mill")).toBeTruthy();
  });

  it("carries the rule's plain-language verdict and reason code into the panel", () => {
    const { getByText } = renderWithProviders(<BatchItemDetail row={_checked} />);
    expect(getByText(/not the brand on the application/i)).toBeTruthy();
    expect(getByText("BRAND.NAME.MISMATCH")).toBeTruthy();
  });

  it("says a label was not checked rather than rendering an empty panel", () => {
    const refused = _row([], [
      {
        rule_id: "ENGINE.INPUT.LABEL_IMAGE_MISSING",
        disposition: "needs_review",
        evidence_ref: "engine_failure/ENGINE.INPUT.LABEL_IMAGE_MISSING",
      },
    ]);
    const { getByText } = renderWithProviders(<BatchItemDetail row={refused} />);
    expect(getByText(/No field on this label was checked/i)).toBeTruthy();
    expect(getByText("ENGINE.INPUT.LABEL_IMAGE_MISSING")).toBeTruthy();
  });

  it("names the engine failure, not the rule-pack row that precedes every trace", () => {
    // per_rule_trace[0] is ENGINE.RULE_PACK.SELECTED on every envelope, because
    // which rules answered is recorded before anything can go wrong. Reading
    // that row told the reviewer rule-pack selection was recorded against their
    // label. The trace below is the one the live service produced for a check
    // the evaluation guard stopped.
    const stopped = _row([], [
      {
        rule_id: "ENGINE.RULE_PACK.SELECTED",
        disposition: "needs_review",
        evidence_ref: "rule_pack/spirits",
      },
      {
        rule_id: "ENGINE.SLA.TIMEOUT",
        disposition: "needs_review",
        evidence_ref: "engine_failure/TimeoutError",
      },
    ]);
    const { getByText, queryByText } = renderWithProviders(<BatchItemDetail row={stopped} />);
    expect(getByText("ENGINE.SLA.TIMEOUT")).toBeTruthy();
    expect(queryByText("ENGINE.RULE_PACK.SELECTED")).toBeNull();
  });

  it("marks a stopped check as incomplete even though it came back with fields", () => {
    // The guard returns what a stopped check had finished rather than nothing,
    // so a partial result now has field cards on it. Without this, those cards
    // read as a completed check.
    const stoppedWithFields = _row(
      [_field("brand_name", "Old Mill Rye", "Olde Mill Rye", [])],
      [
        {
          rule_id: "ENGINE.RULE_PACK.SELECTED",
          disposition: "needs_review",
          evidence_ref: "rule_pack/spirits",
        },
        {
          rule_id: "ENGINE.SLA.TIMEOUT",
          disposition: "needs_review",
          evidence_ref: "engine_failure/TimeoutError",
        },
      ],
    );
    const { getByText } = renderWithProviders(<BatchItemDetail row={stoppedWithFields} />);
    expect(getByText(/stopped before it finished/i)).toBeTruthy();
    expect(getByText("Old Mill Rye")).toBeTruthy();
  });

  it("moves focus onto the opened label so a keyboard reviewer lands on it", () => {
    renderWithProviders(<BatchItemDetail row={_checked} />);
    expect(document.activeElement?.textContent).toBe("lbl-1");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<BatchItemDetail row={_checked} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
