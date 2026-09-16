import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { LiveRegion } from "./LiveRegion";

describe("LiveRegion", () => {
  it("renders aria-live=polite by default", () => {
    const { getByRole } = renderWithProviders(<LiveRegion message="Saved" />);
    const el = getByRole("status");
    expect(el).toHaveAttribute("aria-live", "polite");
    expect(el).toHaveTextContent("Saved");
  });

  it("supports aria-live=assertive when politeness=assertive", () => {
    const { getByRole } = renderWithProviders(
      <LiveRegion politeness="assertive" message="Critical" />,
    );
    const el = getByRole("alert");
    expect(el).toHaveAttribute("aria-live", "assertive");
  });

  it("is visually hidden but exposed to AT", () => {
    const { getByRole } = renderWithProviders(<LiveRegion message="x" />);
    expect(getByRole("status").className).toMatch(/sr-only|absolute/);
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<LiveRegion message="Hello" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
