import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { BboxOverlay } from "./BboxOverlay";

// Two corners each, `[x0, y0, x1, y1]`, which is what the reader emits.
const _bboxes = [
  { id: "a", bbox: [10, 10, 50, 30] as [number, number, number, number], label: "Brand" },
  { id: "b", bbox: [70, 80, 110, 100] as [number, number, number, number], label: "ABV" },
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

  it("draws each box as the two corners the reader reports, not width and height", async () => {
    // The backend emits (x0, y0, x1, y1) from `_Box.as_bbox()`. Read as
    // [x, y, width, height] the first box would be 50 wide and 30 tall and
    // would run off its own label; it is 40 by 20, starting at (10, 10).
    const { container } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} />,
    );
    const rects = Array.from(container.querySelectorAll("rect"));
    expect(rects).toHaveLength(2);
    expect(rects[0]).toHaveAttribute("x", "10");
    expect(rects[0]).toHaveAttribute("y", "10");
    expect(rects[0]).toHaveAttribute("width", "40");
    expect(rects[0]).toHaveAttribute("height", "20");
    expect(rects[1]).toHaveAttribute("x", "70");
    expect(rects[1]).toHaveAttribute("y", "80");
    expect(rects[1]).toHaveAttribute("width", "40");
    expect(rects[1]).toHaveAttribute("height", "20");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <BboxOverlay imageSrc="/x.png" imageWidth={200} imageHeight={150} bboxes={_bboxes} altText="Label" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
