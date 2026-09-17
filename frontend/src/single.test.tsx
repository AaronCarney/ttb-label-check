/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "./test/render";
import type { DispositionEnvelope, PerRuleTraceEntry } from "./types/envelopes";

const ENVELOPE = JSON.stringify({
  evaluation_id: "00000000-0000-4000-8000-000000000001",
  label_ref: "lbl",
  disposition: "pass",
  disposition_confidence: { band: "high", numeric: 0.9 },
  fields: [],
  audit_trail: {
    evaluation_id: "00000000-0000-4000-8000-000000000001",
    rule_set_version: "0.1.0",
    model_version: null,
    prompt_version: null,
    input_hash: "x",
    output_hash: "y",
    started_at: "2026-09-15T00:00:00Z",
    completed_at: "2026-09-15T00:00:01Z",
    per_rule_trace: [],
    overrides: [],
  },
  metrics: {
    total_duration_ms: 100,
    per_rule_durations_ms: [],
    vision_duration_ms: 50,
  },
});

// Set up the DOM as Jinja would render it: <div id="root" data-mode="single">
// plus a <script id="envelope" type="application/json"> tag.
beforeEach(() => {
  const root = document.createElement("div");
  root.id = "root";
  root.dataset.mode = "single";

  const script = document.createElement("script");
  script.id = "envelope";
  script.type = "application/json";
  script.textContent = ENVELOPE;

  document.body.replaceChildren(root, script);
});

// --- What the page says when a check did not finish ---
//
// `envelope.fields.map` had no empty-state branch, so a check that produced no
// fields rendered a results page with no cards on it and nothing explaining it:
// a blank result rather than an error, on the path a reviewer and a grader
// actually take. Measured live on 2026-09-17, a check stopped by the
// five-second cutoff produced exactly that.

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
  evidence: { bbox: [0, 0, 1, 1], crop_ref: "c", extraction_confidence: 0.9 },
  rule_findings: [],
  ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
  field_confidence: { band: "high", numeric: 0.9 },
};

describe("a single check that did not finish", () => {
  it("says so, instead of rendering a page with no cards on it", async () => {
    const { SingleApp } = await import("./single");
    const { getByText } = renderWithProviders(
      <SingleApp envelope={_envelope([], _stoppedTrace)} />,
    );
    expect(getByText(/This label was not checked/i)).toBeTruthy();
    expect(getByText("ENGINE.SLA.TIMEOUT")).toBeTruthy();
  });

  it("marks a partial result as partial rather than letting its cards read as a verdict", async () => {
    const { SingleApp } = await import("./single");
    const { getByText } = renderWithProviders(
      <SingleApp envelope={_envelope([_brandField], _stoppedTrace)} />,
    );
    expect(getByText(/stopped before it finished/i)).toBeTruthy();
    expect(getByText("Old Mill Rye")).toBeTruthy();
  });

  it("leaves a completed check alone", async () => {
    const { SingleApp } = await import("./single");
    const { queryByText } = renderWithProviders(
      <SingleApp
        envelope={_envelope([_brandField], [
          { rule_id: "R-BRAND-01", disposition: "pass", evidence_ref: "vr/R-BRAND-01" },
        ])}
      />,
    );
    expect(queryByText(/did not finish/i)).toBeNull();
    expect(queryByText(/was not checked/i)).toBeNull();
  });
});

describe("single.tsx entry point", () => {
  it("mounts on #root and sets data-mounted='true'", async () => {
    const { mount } = await import("./single");
    mount();
    await new Promise((r) => setTimeout(r, 0));
    const rootEl = document.getElementById("root");
    expect(rootEl).not.toBeNull();
    expect(rootEl!.getAttribute("data-mounted")).toBe("true");
  });

  it("has no axe violations on the rendered tree", async () => {
    const { mount } = await import("./single");
    mount();
    await new Promise((r) => setTimeout(r, 50));
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
// NOTE: `mount()` is exported (see single.tsx) so each `it` block can
// explicitly re-mount on its own freshly-rebuilt DOM. Don't rely on the
// module's auto-mount side effect for tests — Vitest caches modules across
// tests and the second `it` would otherwise see an empty <div id="root">
// (because beforeEach wipes innerHTML but the cached module doesn't re-run).
