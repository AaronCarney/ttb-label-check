import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { CitationChip } from "./CitationChip";

describe("CitationChip", () => {
  it("renders citation text inside a button", () => {
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §5.65(b)" onOpen={() => {}} />,
    );
    const btn = getByRole("button");
    expect(btn).toHaveTextContent("27 CFR §5.65(b)");
  });

  it("calls onOpen on click and Enter", async () => {
    const onOpen = vi.fn();
    const { getByRole } = renderWithProviders(
      <CitationChip citation="27 CFR §16.21" onOpen={onOpen} />,
    );
    const btn = getByRole("button");
    const user = userEvent.setup();
    await user.click(btn);
    btn.focus();
    await user.keyboard("{Enter}");
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <CitationChip citation="27 CFR §4.33" onOpen={() => {}} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
