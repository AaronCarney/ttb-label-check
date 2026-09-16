import { describe, it, expect, vi } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { Toast } from "./Toast";

describe("Toast", () => {
  it("renders with role=status and aria-live=polite", () => {
    const { getByRole } = renderWithProviders(
      <Toast message="Override saved." />,
    );
    const el = getByRole("status");
    expect(el).toHaveAttribute("aria-live", "polite");
    expect(el).toHaveTextContent("Override saved.");
  });

  it("calls onDismiss after the default duration (4000 ms)", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    renderWithProviders(<Toast message="Saved" onDismiss={onDismiss} />);
    vi.advanceTimersByTime(4000);
    expect(onDismiss).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("respects custom duration", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    renderWithProviders(
      <Toast message="x" duration={1000} onDismiss={onDismiss} />,
    );
    vi.advanceTimersByTime(999);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onDismiss).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<Toast message="Hi" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
