import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { RawJSONDrawer } from "./RawJSONDrawer";

const _payload = { evaluation_id: "abc", x: 1 };

describe("RawJSONDrawer", () => {
  it("renders nothing when enabled=false", () => {
    const { container } = renderWithProviders(
      <RawJSONDrawer enabled={false} payload={_payload} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("opens a dialog showing pretty-printed JSON when toggled", async () => {
    const { getByRole } = renderWithProviders(
      <RawJSONDrawer enabled={true} payload={_payload} />,
    );
    const user = userEvent.setup();
    await user.click(getByRole("button", { name: /Show raw JSON/i }));
    const dialog = getByRole("dialog");
    expect(dialog).toHaveTextContent(/"evaluation_id"/);
    expect(dialog).toHaveTextContent(/"abc"/);
  });

  it("has no axe violations when enabled and closed", async () => {
    const { container } = renderWithProviders(
      <RawJSONDrawer enabled={true} payload={_payload} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
