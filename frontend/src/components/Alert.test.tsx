import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { Alert } from "./Alert";

describe("Alert", () => {
  it("renders with role=alert for severity=error", () => {
    const { getByRole } = renderWithProviders(
      <Alert severity="error" title="Format rejected" message="WebP not supported." />,
    );
    const el = getByRole("alert");
    expect(el).toHaveAttribute("aria-live", "assertive");
    expect(el).toHaveTextContent(/Format rejected/);
    expect(el).toHaveTextContent(/WebP not supported/);
  });

  it("renders with role=status for severity=info", () => {
    const { getByRole } = renderWithProviders(
      <Alert severity="info" title="Heads up" message="The model is warming." />,
    );
    const el = getByRole("status");
    expect(el).toHaveAttribute("aria-live", "polite");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <>
        <Alert severity="error" title="A" message="B" />
        <Alert severity="info" title="C" message="D" />
        <Alert severity="warning" title="E" message="F" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
