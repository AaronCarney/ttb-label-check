import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { ReasonCodePicker } from "./ReasonCodePicker";

const _codes = [
  { code: "BRAND.NAME.MISMATCH", description: "Brand mismatch" },
  { code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS", description: "Heading not bold caps" },
  { code: "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", description: "ABV out of band" },
  { code: "CLASS_TYPE.SOI.NO_MATCH", description: "Class/Type SOI mismatch" },
];

describe("ReasonCodePicker", () => {
  it("filters codes by typed prefix (case-insensitive)", async () => {
    const { getByRole, getAllByRole } = renderWithProviders(
      <ReasonCodePicker codes={_codes} onSelect={() => {}} />,
    );
    const input = getByRole("combobox");
    const user = userEvent.setup();
    await user.type(input, "war");
    const options = getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent(/WARNING\.STYLE/);
  });

  it("calls onSelect when a unique-prefix character is typed", async () => {
    const onSelect = vi.fn();
    const { getByRole } = renderWithProviders(
      <ReasonCodePicker codes={_codes} onSelect={onSelect} />,
    );
    const user = userEvent.setup();
    const input = getByRole("combobox");
    await user.type(input, "w"); // 'W' is unique to WARNING.* in the corpus.
    expect(onSelect).toHaveBeenCalledWith("WARNING.STYLE.HEADING_NOT_BOLD_CAPS");
  });

  it("does not auto-select on ambiguous prefix", async () => {
    const onSelect = vi.fn();
    const ambig = [
      ..._codes,
      { code: "WARNING.LEGIBILITY.LOW_RESOLUTION", description: "Low res" },
    ];
    const { getByRole } = renderWithProviders(
      <ReasonCodePicker codes={ambig} onSelect={onSelect} />,
    );
    const user = userEvent.setup();
    await user.type(getByRole("combobox"), "w");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ENTER selects the highlighted option", async () => {
    const onSelect = vi.fn();
    const { getByRole } = renderWithProviders(
      <ReasonCodePicker codes={_codes} onSelect={onSelect} />,
    );
    const user = userEvent.setup();
    const input = getByRole("combobox");
    await user.type(input, "br");
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("BRAND.NAME.MISMATCH");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <ReasonCodePicker codes={_codes} onSelect={() => {}} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
