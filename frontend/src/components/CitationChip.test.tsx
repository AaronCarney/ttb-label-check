/** @vitest-environment jsdom */
import { describe, it, expect, vi } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { CitationChip } from "./CitationChip";

describe("CitationChip", () => {
  it("renders the citation as text", () => {
    const { getByText } = renderWithProviders(<CitationChip citation="27 CFR §5.65(b)" />);
    expect(getByText("27 CFR §5.65(b)")).toBeInTheDocument();
  });

  // `docs/decisions.md#0034` made the chip static because its `onOpen` was
  // never supplied, so pressing it did nothing — "the one thing a reviewer
  // cannot check for themselves". The rule that came out of that is kept
  // literally: the chip is a control only where something opens.
  it("is not a control when nothing opens", () => {
    const { queryByRole } = renderWithProviders(<CitationChip citation="27 CFR §16.21" />);
    expect(queryByRole("button")).toBeNull();
    expect(queryByRole("link")).toBeNull();
  });

  it("is a button when a citation can be opened", () => {
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={vi.fn()} />,
    );
    expect(getByRole("button", { name: /27 CFR §4.33/ })).toBeInTheDocument();
  });

  it("passes the citation back when pressed", () => {
    const onOpen = vi.fn();
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={onOpen} />,
    );
    getByRole("button").click();
    expect(onOpen).toHaveBeenCalledWith("27 CFR §4.33");
  });

  // A button is reached by Tab and fired by Enter and Space without anything
  // here doing so on purpose. The assertion is that nothing has taken that
  // away — no tabIndex of -1, no div dressed as a button, no hover handler
  // standing in for the press.
  it("is reachable by keyboard", () => {
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={vi.fn()} />,
    );
    const button = getByRole("button");
    expect(button.tagName).toBe("BUTTON");
    expect(button).not.toHaveAttribute("tabindex", "-1");
    button.focus();
    expect(document.activeElement).toBe(button);
  });

  it("says which citation is the one on show", () => {
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={vi.fn()} selected />,
    );
    expect(getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("points at the panel it fills", () => {
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={vi.fn()} controls="citation-panel" />,
    );
    expect(getByRole("button")).toHaveAttribute("aria-controls", "citation-panel");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={vi.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
