import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { BatchTable } from "./BatchTable";
import type { BatchSSEEvent } from "../types/sse";

const _stubRow = (i: number, disposition: "pass" | "fail" | "needs_review"): BatchSSEEvent => ({
  batch_id: "B",
  queue_position: i,
  evaluation_id: `e${i}`,
  label_ref: `lbl-${i}`,
  disposition,
  disposition_confidence: { band: "high", numeric: 0.9 },
  fields: [],
  audit_trail: {
    evaluation_id: `e${i}`,
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
    total_duration_ms: 1000,
    per_rule_durations_ms: [],
    vision_duration_ms: 500,
    orchestrator_duration_ms: 0,
  },
});

describe("BatchTable", () => {
  const rows = [_stubRow(1, "pass"), _stubRow(2, "fail"), _stubRow(3, "needs_review")];

  it("renders one row per item with disposition pill", () => {
    const { getAllByRole } = renderWithProviders(
      <BatchTable rows={rows} onSelect={() => {}} />,
    );
    // 1 header row + 3 data rows = 4.
    expect(getAllByRole("row")).toHaveLength(4);
  });

  it("sorts by queue position ascending by default; toggles on header click", async () => {
    const desc = [_stubRow(3, "pass"), _stubRow(1, "fail"), _stubRow(2, "pass")];
    const { getAllByRole, getByRole } = renderWithProviders(
      <BatchTable rows={desc} onSelect={() => {}} />,
    );
    const positions = () =>
      getAllByRole("row").slice(1).map((r) => r.querySelector('[data-col="position"]')?.textContent);
    expect(positions()).toEqual(["1", "2", "3"]);
    const user = userEvent.setup();
    await user.click(getByRole("button", { name: /Sort by Position/i }));
    expect(positions()).toEqual(["3", "2", "1"]);
  });

  it("calls onSelect on row click and Enter keypress", async () => {
    const onSelect = vi.fn();
    const { getAllByRole } = renderWithProviders(
      <BatchTable rows={rows} onSelect={onSelect} />,
    );
    const user = userEvent.setup();
    const dataRows = getAllByRole("row").slice(1);
    await user.click(dataRows[1]!);
    expect(onSelect).toHaveBeenLastCalledWith("lbl-2");
    dataRows[2]!.focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith("lbl-3");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <BatchTable rows={rows} onSelect={() => {}} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
