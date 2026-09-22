/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { LabelResult } from "./LabelResult";
import type { DispositionEnvelope, PerRuleTraceEntry } from "../types/envelopes";

// The component asks the server which photographs it holds. Every test here is
// about the findings, so the answer is "none" unless a test says otherwise.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => ({ faces: [] }) })),
  );
});

const _auditTrail = (trace: PerRuleTraceEntry[]) => ({
  evaluation_id: "ev-1",
  rule_set_version: "0.1.0",
  model_version: null,
  prompt_version: null,
  input_hash: "x",
  output_hash: "y",
  started_at: "2026-09-17T00:00:00Z",
  completed_at: "2026-09-17T00:00:05Z",
  per_rule_trace: trace,
  overrides: [],
});

const _envelope = (
  fields: DispositionEnvelope["fields"],
  trace: PerRuleTraceEntry[],
): DispositionEnvelope => ({
  evaluation_id: "ev-1",
  label_ref: "lbl-1",
  disposition: "needs_review",
  disposition_confidence: { band: "low", numeric: 0 },
  fields,
  audit_trail: _auditTrail(trace),
  metrics: {
    total_duration_ms: 5001,
    per_rule_durations_ms: [],
    vision_duration_ms: 4900,
    cache_hit: false,
  },
});

const _stoppedTrace: PerRuleTraceEntry[] = [
  { rule_id: "ENGINE.RULE_PACK.SELECTED", disposition: "not_applicable", evidence_ref: "rule_pack/spirits" },
  { rule_id: "ENGINE.SLA.TIMEOUT", disposition: "needs_review", evidence_ref: "engine_failure/TimeoutError" },
];

const _brandField: DispositionEnvelope["fields"][number] = {
  field_name: "brand_name",
  extracted_value: "Old Mill Rye",
  expected_value: "Olde Mill Rye",
  evidence: { bbox: [0, 0, 1, 1], crop_ref: "c", extraction_confidence: 0.9, face_tag: "front" },
  rule_findings: [],
  ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
  field_confidence: { band: "high", numeric: 0.9 },
};

// --- What the page says when a check did not finish ---
//
// `envelope.fields.map` had no empty-state branch, so a check that produced no
// fields rendered a page with no cards on it and nothing explaining it: a blank
// result rather than an error, on the path a reviewer and a grader actually
// take. Measured live, a check stopped by the five-second cutoff produced
// exactly that.
describe("a check that did not finish", () => {
  it("says so, instead of rendering a page with no cards on it", () => {
    const { getByText } = renderWithProviders(
      <LabelResult envelope={_envelope([], _stoppedTrace)} />,
    );
    expect(getByText(/This label was not checked/i)).toBeTruthy();
    expect(getByText("ENGINE.SLA.TIMEOUT")).toBeTruthy();
  });

  it("marks a partial result as partial rather than letting its cards read as a verdict", () => {
    const { getByText } = renderWithProviders(
      <LabelResult envelope={_envelope([_brandField], _stoppedTrace)} />,
    );
    expect(getByText(/stopped before it finished/i)).toBeTruthy();
    expect(getByText("Old Mill Rye")).toBeTruthy();
  });

  it("leaves a completed check alone", () => {
    const { queryByText } = renderWithProviders(
      <LabelResult
        envelope={_envelope([_brandField], [
          { rule_id: "R-BRAND-01", disposition: "pass", evidence_ref: "vr/R-BRAND-01" },
        ])}
      />,
    );
    expect(queryByText(/did not finish/i)).toBeNull();
    expect(queryByText(/was not checked/i)).toBeNull();
  });
});

describe("a photo the reader found no text on", () => {
  it("asks for a better photo of that face, not a resubmission", () => {
    const { getByText, getByRole, queryByText } = renderWithProviders(
      <LabelResult
        envelope={_envelope([], [
          {
            rule_id: "LEGIBILITY.PHOTO.NO_TEXT",
            disposition: "needs_review",
            evidence_ref: "engine_failure/LEGIBILITY.PHOTO.NO_TEXT/back",
          },
        ])}
      />,
    );
    expect(getByRole("region", { name: "Needs better photo" })).toBeTruthy();
    expect(getByText(/No text could be found on the back photo/)).toBeTruthy();
    expect(queryByText(/was not checked/i)).toBeNull();
    expect(queryByText(/on its own/i)).toBeNull();
  });
});

describe("the photographs the check was made from", () => {
  it("shows every face the server says it holds, each named", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          faces: [
            { tag: "front", caption: "Front", url: "/labels/ev-1/image?face=front" },
            { tag: "back", caption: "Back", url: "/labels/ev-1/image?face=back" },
          ],
        }),
      })),
    );
    const { findAllByRole, getByText } = renderWithProviders(
      <LabelResult envelope={_envelope([_brandField], [])} />,
    );
    const images = await findAllByRole("img");
    expect(images.map((img) => img.getAttribute("src"))).toEqual([
      "/labels/ev-1/image?face=front",
      "/labels/ev-1/image?face=back",
    ]);
    // Two images described identically are two images a screen reader user
    // cannot tell apart (NFR-3), and the whole point of showing the back is
    // that a warning finding is read against the face that carries it.
    const alts = images.map((img) => img.getAttribute("alt"));
    expect(new Set(alts).size).toBe(2);
    // And named on the page too, for a reviewer who can see them.
    expect(getByText(/^Front —/)).toBeTruthy();
    expect(getByText(/^Back —/)).toBeTruthy();
  });

  it("renders the findings anyway when the photographs cannot be listed", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    const { getByText, queryAllByRole } = renderWithProviders(
      <LabelResult envelope={_envelope([_brandField], [])} />,
    );
    await new Promise((r) => setTimeout(r, 0));
    expect(getByText("Old Mill Rye")).toBeTruthy();
    expect(queryAllByRole("img")).toHaveLength(0);
  });
});

describe("before the first result arrives", () => {
  it("says the first label to finish will open here", () => {
    const { getByText } = renderWithProviders(<LabelResult envelope={null} />);
    expect(getByText(/first label to finish opens here/i)).toBeTruthy();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <LabelResult envelope={_envelope([_brandField], [])} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
