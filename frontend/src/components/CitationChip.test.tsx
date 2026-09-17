import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { CitationChip } from "./CitationChip";

describe("CitationChip", () => {
  it("renders the citation as text", () => {
    const { getByText } = renderWithProviders(<CitationChip citation="27 CFR §5.65(b)" />);
    expect(getByText("27 CFR §5.65(b)")).toBeInTheDocument();
  });

  // It used to be a button, with an `onOpen` neither call site ever passed, so
  // a reviewer could press it and nothing happened. It stays text until the
  // product can show the section it names (`docs/decisions.md#0034`).
  it("is not a control", () => {
    const { queryByRole } = renderWithProviders(<CitationChip citation="27 CFR §16.21" />);
    expect(queryByRole("button")).toBeNull();
    expect(queryByRole("link")).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<CitationChip citation="27 CFR §4.33" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
