/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach } from "vitest";
import { axe } from "vitest-axe";

// Stub EventSource as a no-op for the entry-point smoke; full SSE behavior is
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
  document.body.innerHTML = `<div id="root" data-mode="batch" data-batch-id="abc-123"></div>`;
});

// NOTE: `mount()` is exported from batch.tsx so each `it` block can re-mount
// explicitly. Vitest caches modules, so relying on the auto-mount side
// effect would render only on the first `it` block (subsequent ones would
// see the empty <div id="root"> that beforeEach restored).
describe("batch.tsx entry point", () => {
  it("mounts and reads data-batch-id", async () => {
    const { mount } = await import("./batch");
    mount();
    await new Promise((r) => setTimeout(r, 0));
    const root = document.getElementById("root");
    expect(root!.getAttribute("data-mounted")).toBe("true");
    expect(document.body.textContent).toContain("abc-123");
  });

  it("has no axe violations on the empty-state render", async () => {
    const { mount } = await import("./batch");
    mount();
    await new Promise((r) => setTimeout(r, 50));
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
