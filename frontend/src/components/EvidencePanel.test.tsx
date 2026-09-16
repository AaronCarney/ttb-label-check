import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { EvidencePanel } from "./EvidencePanel";

describe("EvidencePanel", () => {
  it("renders citation header, regulation text, and evidence side by side", () => {
    const { getByText, getByRole } = renderWithProviders(
      <EvidencePanel
        open
        onOpenChange={() => {}}
        citation="27 CFR §5.65(b)"
        regulationText="ABV statement must …"
        evidenceText="Label says: 45% ALC/VOL."
      />,
    );
    expect(getByRole("dialog")).toBeInTheDocument();
    expect(getByText(/27 CFR §5.65/)).toBeInTheDocument();
    expect(getByText(/ABV statement must/)).toBeInTheDocument();
    expect(getByText(/45% ALC\/VOL/)).toBeInTheDocument();
  });

  it("calls onOpenChange(false) when the close button is clicked", async () => {
    const onOpenChange = vi.fn();
    const { getByRole } = renderWithProviders(
      <EvidencePanel
        open
        onOpenChange={onOpenChange}
        citation="x"
        regulationText="y"
        evidenceText="z"
      />,
    );
    const user = userEvent.setup();
    await user.click(getByRole("button", { name: /close/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("has no axe violations when open", async () => {
    const { container } = renderWithProviders(
      <EvidencePanel open onOpenChange={() => {}} citation="x" regulationText="y" evidenceText="z" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
