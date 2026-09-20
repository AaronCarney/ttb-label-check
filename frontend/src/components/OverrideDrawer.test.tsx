import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { OverrideDrawer } from "./OverrideDrawer";

const _codes = [
  { code: "BRAND.NAME.MISMATCH", description: "Brand mismatch" },
  { code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS", description: "Heading not bold caps" },
  { code: "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", description: "ABV out of band" },
];

describe("OverrideDrawer", () => {
  it("renders nothing when open=false", () => {
    const { queryByRole } = renderWithProviders(
      <OverrideDrawer open={false} onOpenChange={() => {}} codes={_codes} onSubmit={() => {}} />,
    );
    expect(queryByRole("dialog")).toBeNull();
  });

  it("auto-focuses the picker when opened, where the 'O' keystroke lands", () => {
    const { getByRole } = renderWithProviders(
      <OverrideDrawer open={true} onOpenChange={() => {}} codes={_codes} onSubmit={() => {}} />,
    );
    expect(getByRole("combobox")).toHaveFocus();
  });

  it("O→reason→ENTER completes an override in three keystrokes", async () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <OverrideDrawer open={true} onOpenChange={() => {}} codes={_codes} onSubmit={onSubmit} />,
    );
    const user = userEvent.setup();
    // Keystroke 1 ('O') was the parent-level shortcut that opened this drawer.
    // Keystroke 2: type 'W' (unique prefix → picker auto-selects WARNING.*).
    await user.keyboard("w");
    // Keystroke 3: ENTER → submit.
    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledWith({
      reasonCode: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
      justification: "",
    });
  });

  // Mirrors the `REASON_CODES` shape in LabelResult.tsx — three W-prefixed entries
  // means typing 'w' does NOT trigger auto-resolve; ENTER must submit on
  // filtered[highlight=0]. Locks down the Playwright-only path the original
  // unit test masked.
  it("highlight=0+ENTER submits when the prefix is not unique", async () => {
    const codesMulti = [
      { code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS", description: "Heading not bold caps" },
      { code: "WARNING.LEGIBILITY.LOW_RESOLUTION", description: "Low resolution" },
      { code: "WARNING.LEGIBILITY.GLARE", description: "Glare" },
    ];
    const onSubmit = vi.fn();
    renderWithProviders(
      <OverrideDrawer open={true} onOpenChange={() => {}} codes={codesMulti} onSubmit={onSubmit} />,
    );
    const user = userEvent.setup();
    await user.keyboard("w");
    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledWith({
      reasonCode: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS",
      justification: "",
    });
  });

  it("ESC closes the drawer (calls onOpenChange(false))", async () => {
    const onOpenChange = vi.fn();
    renderWithProviders(
      <OverrideDrawer open={true} onOpenChange={onOpenChange} codes={_codes} onSubmit={() => {}} />,
    );
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("has no axe violations when open", async () => {
    const { container } = renderWithProviders(
      <OverrideDrawer open={true} onOpenChange={() => {}} codes={_codes} onSubmit={() => {}} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
