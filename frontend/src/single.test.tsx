/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach } from "vitest";
import { axe } from "vitest-axe";

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
