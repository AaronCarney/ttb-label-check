import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { DispositionPill } from "./DispositionPill";

describe("DispositionPill", () => {
  it.each([
    ["pass", "Pass", "check"],
    ["fail", "Fail", "x"],
    ["needs_review", "Needs review", "question"],
  ] as const)("renders %s with text + shape", (disposition, label, shape) => {
    const { getByRole } = renderWithProviders(
      <DispositionPill disposition={disposition} />,
    );
    const pill = getByRole("status");
    expect(pill).toHaveTextContent(label);
    expect(pill.querySelector(`[data-shape="${shape}"]`)).not.toBeNull();
  });

  it("encodes disposition in three channels, not by colour alone", () => {
    const { getByRole } = renderWithProviders(
      <DispositionPill disposition="fail" />,
    );
    const pill = getByRole("status");
    // 1) Text channel.
    expect(pill).toHaveTextContent(/Fail/i);
    // 2) Shape channel — distinct icon per disposition.
    expect(pill.querySelector('[data-shape="x"]')).not.toBeNull();
    // 3) Color channel — applied as a Tailwind class for "fail".
    expect(pill.className).toMatch(/destructive|error/);
  });

  it("exposes aria-label for screen readers", () => {
    const { getByRole } = renderWithProviders(
      <DispositionPill disposition="needs_review" />,
    );
    expect(getByRole("status")).toHaveAttribute(
      "aria-label",
      "Disposition: Needs review",
    );
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <>
        <DispositionPill disposition="pass" />
        <DispositionPill disposition="fail" />
        <DispositionPill disposition="needs_review" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
