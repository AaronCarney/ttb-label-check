import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { ConfidenceIndicator } from "./ConfidenceIndicator";

describe("ConfidenceIndicator", () => {
  it("shows numeric (2 decimals) and band label", () => {
    const { getByRole } = renderWithProviders(
      <ConfidenceIndicator band="high" numeric={0.94} />,
    );
    const el = getByRole("group");
    expect(el).toHaveTextContent("0.94");
    expect(el).toHaveTextContent(/High/i);
  });

  it.each(["high", "medium", "low"] as const)("renders %s band with aria-valuetext", (band) => {
    const { getByRole } = renderWithProviders(
      <ConfidenceIndicator band={band} numeric={0.5} />,
    );
    const meter = getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "1");
    expect(meter).toHaveAttribute("aria-valuenow", "0.5");
    expect(meter).toHaveAttribute(
      "aria-valuetext",
      expect.stringContaining(band),
    );
  });

  it("clamps display values out of [0,1]", () => {
    const { getByRole } = renderWithProviders(
      <ConfidenceIndicator band="low" numeric={1.5} />,
    );
    expect(getByRole("meter")).toHaveAttribute("aria-valuenow", "1");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <ConfidenceIndicator band="medium" numeric={0.62} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
