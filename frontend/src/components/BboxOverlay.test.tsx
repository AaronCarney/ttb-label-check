import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { BboxOverlay } from "./BboxOverlay";

const _bboxes = [
  { id: "a", bbox: [10, 10, 50, 30] as [number, number, number, number], label: "Brand" },
  { id: "b", bbox: [70, 80, 40, 20] as [number, number, number, number], label: "ABV" },
];

describe("BboxOverlay", () => {
  it("renders one focusable button per bbox", () => {
    const { getAllByRole } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} />,
    );
    const btns = getAllByRole("button");
    expect(btns).toHaveLength(2);
    btns.forEach((b) => expect(b).toHaveAttribute("tabindex", "0"));
  });

  it("toggles aria-pressed on Enter and Space", async () => {
    const { getAllByRole } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} />,
    );
    const user = userEvent.setup();
    const first = getAllByRole("button")[0]!;
    first.focus();
    expect(first).toHaveAttribute("aria-pressed", "false");
    await user.keyboard("{Enter}");
    expect(first).toHaveAttribute("aria-pressed", "true");
    await user.keyboard(" ");
    expect(first).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onSelect with the box id on activation", async () => {
    const onSelect = vi.fn();
    const { getAllByRole } = renderWithProviders(
      <BboxOverlay
        imageSrc="/x.png"
        imageWidth={200}
        imageHeight={150}
        bboxes={_bboxes}
        onSelect={onSelect}
      />,
    );
    const user = userEvent.setup();
    await user.click(getAllByRole("button")[1]!);
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("has alt text on the underlying image", () => {
    const { getByRole } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} altText="Front label" />,
    );
    expect(getByRole("img", { name: /Front label/i })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} altText="Label" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
