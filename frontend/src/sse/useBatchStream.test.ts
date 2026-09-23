import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBatchStream } from "./useBatchStream";

// Lightweight fake EventSource that supports addEventListener("<name>", handler)
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  listeners = new Map<string, Set<(ev: MessageEvent) => void>>();
  onerror: ((ev: Event) => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, handler: (ev: MessageEvent) => void) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name)!.add(handler);
  }
  removeEventListener(name: string, handler: (ev: MessageEvent) => void) {
    this.listeners.get(name)?.delete(handler);
  }
  close() { this.closed = true; }
  fire(name: string, data: unknown) {
    if (this.closed) return;  // closed bus drops events
    const event = { data: typeof data === "string" ? data : JSON.stringify(data) } as MessageEvent;
    this.listeners.get(name)?.forEach((h) => h(event));
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function _envelope(label_ref: string, disposition: "pass" | "fail" | "needs_review" = "pass") {
  return {
    evaluation_id: `EV-${label_ref}`,
    label_ref,
    disposition,
    disposition_confidence: { band: "high", numeric: 0.95 },
    fields: [],
    audit_trail: {
      evaluation_id: `EV-${label_ref}`,
      rule_set_version: "t",
      model_version: null,
      prompt_version: null,
      input_hash: "0".repeat(64),
      output_hash: "0".repeat(64),
      started_at: "2026-09-15T00:00:00Z",
      completed_at: "2026-09-15T00:00:00Z",
      per_rule_trace: [],
      overrides: [],
    },
    metrics: {
      total_duration_ms: 10,
      per_rule_durations_ms: [],
      vision_duration_ms: 5,
    },
  };
}

describe("useBatchStream", () => {
  it("pushes label-result events with unwrapped envelope payload", () => {
    const { result } = renderHook(() => useBatchStream("B-001"));
    const es = FakeEventSource.instances[0]!;
    expect(es.url).toContain("/batches/B-001/stream");

    act(() => {
      es.fire("label-result", { batch_id: "B-001", queue_position: 1, envelope: _envelope("lbl-1") });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]!.label_ref).toBe("lbl-1");
    expect(result.current.events[0]!.batch_id).toBe("B-001");
    expect(result.current.events[0]!.queue_position).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("stream-end closes the connection — subsequent label-result events are ignored", () => {
    const { result } = renderHook(() => useBatchStream("B-002"));
    const es = FakeEventSource.instances[0]!;

    act(() => {
      es.fire("label-result", { batch_id: "B-002", queue_position: 1, envelope: _envelope("lbl-A") });
    });
    expect(result.current.events).toHaveLength(1);

    act(() => {
      es.fire("stream-end", {});
    });

    // After stream-end, the EventSource is closed; further fires are dropped.
    act(() => {
      es.fire("label-result", { batch_id: "B-002", queue_position: 2, envelope: _envelope("lbl-B") });
    });
    expect(result.current.events).toHaveLength(1);  // still 1, no lbl-B
    expect(es.closed).toBe(true);
  });

  it("dedupes label-result events with the same label_ref", () => {
    const { result } = renderHook(() => useBatchStream("B-003"));
    const es = FakeEventSource.instances[0]!;

    act(() => {
      es.fire("label-result", { batch_id: "B-003", queue_position: 1, envelope: _envelope("lbl-X") });
      es.fire("label-result", { batch_id: "B-003", queue_position: 2, envelope: _envelope("lbl-X", "fail") });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]!.disposition).toBe("pass");  // first wins
  });

  it("sets error on malformed JSON payload", () => {
    const { result } = renderHook(() => useBatchStream("B-004"));
    const es = FakeEventSource.instances[0]!;

    act(() => {
      es.fire("label-result", "not-json{");
    });

    expect(result.current.error).toBe("Malformed SSE payload");
  });

  // A reviewer's correction moves the label's row in the batch table, whether
  // it arrives on the stream or, once the batch has finished and the stream is
  // closed, from the page's own request. Hearing it both ways applies it once.
  it("applies a correction to its label, once, from either source", () => {
    const { result } = renderHook(() => useBatchStream("B-005"));
    const es = FakeEventSource.instances[0]!;
    const entry = {
      field_name: "brand_name",
      original_disposition: "fail",
      applied_disposition: "pass",
      reason_code: "REVIEWER.CORRECTION.PASS",
      justification_text: null,
      reviewer_id: "session-a",
      timestamp: "2026-09-22T00:00:00Z",
    } as const;

    act(() => {
      es.fire("label-result", { batch_id: "B-005", queue_position: 1, envelope: _envelope("lbl-1", "fail") });
      es.fire("label-result", { batch_id: "B-005", queue_position: 2, envelope: _envelope("lbl-2", "fail") });
    });
    act(() => {
      es.fire("override-applied", {
        batch_id: "B-005",
        evaluation_id: "EV-lbl-1",
        entry,
        label_disposition: "pass",
      });
    });
    act(() => {
      result.current.applyOverride("EV-lbl-1", { entry, labelDisposition: "pass" });
    });

    const [first, second] = result.current.events;
    expect(first!.disposition).toBe("pass");
    expect(first!.audit_trail.overrides).toHaveLength(1);
    expect(first!.batch_id).toBe("B-005");
    expect(second!.disposition).toBe("fail");
  });
});
