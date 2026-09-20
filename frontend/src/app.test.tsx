/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { axe } from "vitest-axe";

// Stub EventSource as a no-op for the entry-point smoke; full SSE behaviour is
// covered by useBatchStream.test.ts.
class _NoopEventSource {
  onmessage: unknown = null;
  onerror: unknown = null;
  close(): void {}
  addEventListener(): void {}
  removeEventListener(): void {}
}

beforeEach(() => {
  (globalThis as unknown as { EventSource: unknown }).EventSource = _NoopEventSource;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => ({ faces: [] }) })),
  );
  // As base.html renders it: the island mounts inside the page's <main>
  // landmark, so it renders a <div> and not a second <main> of its own.
  document.body.innerHTML = `<main id="main"><div id="root" data-batch-id="abc-123"></div></main>`;
});

// NOTE: `mount()` is exported from app.tsx so each `it` block can re-mount
// explicitly. Vitest caches modules, so relying on the auto-mount side effect
// would render only on the first `it` block (subsequent ones would see the
// empty <div id="root"> that beforeEach restored).
describe("app.tsx entry point", () => {
  it("mounts and reads data-batch-id", async () => {
    const { mount } = await import("./app");
    mount();
    await new Promise((r) => setTimeout(r, 0));
    const root = document.getElementById("root");
    expect(root!.getAttribute("data-mounted")).toBe("true");
  });

  it("says a result is coming rather than showing an empty page", async () => {
    const { mount } = await import("./app");
    mount();
    await new Promise((r) => setTimeout(r, 0));
    expect(document.body.textContent).toContain("first result appears as soon as it is ready");
  });

  it("has no axe violations on the empty-state render", async () => {
    const { mount } = await import("./app");
    mount();
    await new Promise((r) => setTimeout(r, 50));
    expect(await axe(document.body)).toHaveNoViolations();
  });
});

// --- One graded item per moment, and the whole submission processed behind it ---
//
// The engine has always broadcast each label's result as it landed. What a
// reviewer met was a table and an instruction to choose a row, so the product
// held a finished verdict back behind a click. These are the two claims the
// merged page makes: the first result opens itself, and the list of everything
// else appears only when there is something else.

class _FakeEventSource {
  static instances: _FakeEventSource[] = [];
  url: string;
  listeners = new Map<string, Set<(ev: MessageEvent) => void>>();
  onerror: ((ev: Event) => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    _FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, handler: (ev: MessageEvent) => void) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name)!.add(handler);
  }
  removeEventListener(name: string, handler: (ev: MessageEvent) => void) {
    this.listeners.get(name)?.delete(handler);
  }
  close() {
    this.closed = true;
  }
  fire(name: string, data: unknown) {
    if (this.closed) return;
    this.listeners.get(name)?.forEach((h) => h({ data: JSON.stringify(data) } as MessageEvent));
  }
}

function _result(labelRef: string, queuePosition: number) {
  return {
    batch_id: "B-1",
    queue_position: queuePosition,
    envelope: {
      evaluation_id: `EV-${labelRef}`,
      label_ref: labelRef,
      disposition: "pass",
      disposition_confidence: { band: "high", numeric: 0.95 },
      fields: [],
      audit_trail: {
        evaluation_id: `EV-${labelRef}`,
        rule_set_version: "t",
        model_version: null,
        prompt_version: null,
        input_hash: "0".repeat(64),
        output_hash: "0".repeat(64),
        started_at: "2026-09-17T00:00:00Z",
        completed_at: "2026-09-17T00:00:00Z",
        per_rule_trace: [{ rule_id: "R-1", disposition: "pass", evidence_ref: "vr/R-1" }],
        overrides: [],
      },
      metrics: { total_duration_ms: 10, per_rule_durations_ms: [], vision_duration_ms: 5 },
    },
  };
}

describe("the results page", () => {
  beforeEach(() => {
    _FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", _FakeEventSource);
  });

  it("opens the first label's findings without being asked", async () => {
    const { act } = await import("@testing-library/react");
    const { renderWithProviders } = await import("./test/render");
    const { ResultsApp } = await import("./app");
    const { findByRole } = renderWithProviders(<ResultsApp batchId="B-1" />);
    // The last instance, not the first: React's strict mode mounts the
    // subscribing effect, tears it down and mounts it again, so the first
    // EventSource this render made is already closed.
    const es = _FakeEventSource.instances[_FakeEventSource.instances.length - 1]!;
    act(() => es.fire("label-result", _result("lucy.jpg", 0)));
    expect(await findByRole("region", { name: /Check results for lucy\.jpg/i })).toBeTruthy();
  });

  it("shows no list of other labels when there is only one", async () => {
    const { act } = await import("@testing-library/react");
    const { renderWithProviders } = await import("./test/render");
    const { ResultsApp } = await import("./app");
    const { queryByRole } = renderWithProviders(<ResultsApp batchId="B-1" />);
    // The last instance, not the first: React's strict mode mounts the
    // subscribing effect, tears it down and mounts it again, so the first
    // EventSource this render made is already closed.
    const es = _FakeEventSource.instances[_FakeEventSource.instances.length - 1]!;
    act(() => es.fire("label-result", _result("lucy.jpg", 0)));
    act(() => es.fire("stream-end", { batch_id: "B-1", total_count: 1, failed_count: 0 }));
    expect(queryByRole("table")).toBeNull();
  });

  it("lists the submission once a second label lands, first still open", async () => {
    const { act } = await import("@testing-library/react");
    const { renderWithProviders } = await import("./test/render");
    const { ResultsApp } = await import("./app");
    const { findByRole, getByRole } = renderWithProviders(<ResultsApp batchId="B-1" />);
    // The last instance, not the first: React's strict mode mounts the
    // subscribing effect, tears it down and mounts it again, so the first
    // EventSource this render made is already closed.
    const es = _FakeEventSource.instances[_FakeEventSource.instances.length - 1]!;
    act(() => es.fire("label-result", _result("lucy.jpg", 0)));
    act(() => es.fire("label-result", _result("maude.jpg", 1)));
    expect(getByRole("table")).toBeTruthy();
    expect(await findByRole("region", { name: /Check results for lucy\.jpg/i })).toBeTruthy();
  });
});

// --- The regulation beside the finding ---
//
// `docs/decisions.md#0046` settled the shape: a reserved column that fills in
// place, never a pop-up and never an overlay, reached from a chip that is a
// button. These are the claims that shape makes on the page.

function _resultWithCitation(labelRef: string) {
  const base = _result(labelRef, 0);
  return {
    ...base,
    envelope: {
      ...base.envelope,
      fields: [
        {
          field_name: "brand_name",
          extracted_value: "Portalupi",
          expected_value: "PORTALUPI",
          field_confidence: { band: "high", numeric: 0.9 },
          evidence: { bbox: [0, 0, 1, 1], crop_ref: "", extraction_confidence: 0.9, face_tag: "front" },
          ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
          rule_findings: [
            {
              rule_id: "wine.brand.present",
              cfr_citation: "27 CFR §4.33",
              disposition: "pass",
              reason_code: "",
              plain_language_explanation: "",
              matched_value: "",
            },
          ],
        },
      ],
    },
  };
}

describe("the regulation panel", () => {
  beforeEach(() => {
    _FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", _FakeEventSource);
  });

  it("holds its column before a reviewer has chosen anything", async () => {
    const { renderWithProviders } = await import("./test/render");
    const { ResultsApp } = await import("./app");
    const { getByRole } = renderWithProviders(<ResultsApp batchId="B-1" />);
    expect(getByRole("region", { name: /the regulation/i })).toBeInTheDocument();
  });

  it("fills in place when a citation is pressed, without a dialog", async () => {
    const { act } = await import("@testing-library/react");
    const { renderWithProviders } = await import("./test/render");
    const { ResultsApp } = await import("./app");

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).startsWith("/cfr")
          ? {
              ok: true,
              json: async () => ({
                citation: "27 CFR §4.33",
                sections: [
                  {
                    key: "title-27-section-4.33",
                    heading: "§ 4.33 Brand names.",
                    text: "The product shall bear a brand name.",
                    paragraph: null,
                    source_url: "https://www.ecfr.gov/x",
                    version_date: "2026-09-16",
                    retrieved: "2026-09-20",
                  },
                ],
              }),
            }
          : { ok: true, json: async () => ({ faces: [] }) },
      ),
    );

    const { findByRole, findByText, queryByRole } = renderWithProviders(
      <ResultsApp batchId="B-1" />,
    );
    const es = _FakeEventSource.instances[_FakeEventSource.instances.length - 1]!;
    act(() => es.fire("label-result", _resultWithCitation("lucy.jpg")));

    const chip = await findByRole("button", { name: /27 CFR §4\.33/ });
    act(() => chip.click());

    expect(await findByText("§ 4.33 Brand names.")).toBeInTheDocument();
    // Filled in place: the regulation is a region of the page, not something
    // laid over it.
    expect(queryByRole("dialog")).toBeNull();
  });
});
