import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { ProcessingTime, formatDuration } from "./ProcessingTime";
import type { Metrics } from "../types/envelopes";

function metrics(over: Partial<Metrics> = {}): Metrics {
  return {
    total_duration_ms: 4200,
    per_rule_durations_ms: [],
    vision_duration_ms: 3100,
    cache_hit: false,
    ...over,
  };
}

describe("formatDuration", () => {
  it("reads below a second in milliseconds, so a cache hit is not '0.0 s'", () => {
    expect(formatDuration(18)).toBe("18 ms");
    expect(formatDuration(999)).toBe("999 ms");
  });

  it("reads a second and over in seconds", () => {
    expect(formatDuration(1000)).toBe("1.0 s");
    expect(formatDuration(4249)).toBe("4.2 s");
  });

  it("floors a negative or non-finite clock reading at zero", () => {
    expect(formatDuration(-5)).toBe("0 ms");
    expect(formatDuration(Number.NaN)).toBe("0 ms");
  });
});

describe("ProcessingTime", () => {
  it("shows how long the check took", () => {
    const { getByText } = renderWithProviders(<ProcessingTime metrics={metrics()} />);
    expect(getByText("Checked in 4.2 s")).toBeTruthy();
  });

  it("says a cached answer is cached, so its near-zero time is not read as the check's", () => {
    const { getByText } = renderWithProviders(
      <ProcessingTime metrics={metrics({ total_duration_ms: 12, cache_hit: true })} />,
    );
    expect(getByText("Served from cache in 12 ms")).toBeTruthy();
  });

  it("says a stopped check was stopped, rather than claiming it was checked", () => {
    const { getByText } = renderWithProviders(
      <ProcessingTime metrics={metrics({ total_duration_ms: 5000 })} stoppedEarly />,
    );
    expect(getByText("Stopped after 5.0 s")).toBeTruthy();
  });

  it("prefers the cache wording when a cached answer is also marked stopped", () => {
    // The stored answer was itself a stopped check. What this request cost is
    // still the cache's cost, which is the claim the number would otherwise
    // make wrongly.
    const { getByText } = renderWithProviders(
      <ProcessingTime metrics={metrics({ total_duration_ms: 3, cache_hit: true })} stoppedEarly />,
    );
    expect(getByText("Served from cache in 3 ms")).toBeTruthy();
  });

  it("renders nothing when there is no measurement, rather than a zero", () => {
    const { queryByTestId } = renderWithProviders(<ProcessingTime metrics={null} />);
    expect(queryByTestId("processing-time")).toBeNull();
  });

  it("offers the vision share as supplementary detail on a real check only", () => {
    const { getByTestId, rerender } = renderWithProviders(<ProcessingTime metrics={metrics()} />);
    expect(getByTestId("processing-time").getAttribute("title")).toBe(
      "Reading the label took 3.1 s of that.",
    );
    rerender(<ProcessingTime metrics={metrics({ cache_hit: true })} />);
    expect(getByTestId("processing-time").getAttribute("title")).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<ProcessingTime metrics={metrics()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
