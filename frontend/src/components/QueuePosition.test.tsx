import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { QueuePosition } from "./QueuePosition";

describe("QueuePosition", () => {
  it("renders 'N of M' with descriptive aria-label", () => {
    const { getByRole } = renderWithProviders(
      <QueuePosition current={3} total={50} />,
    );
    const el = getByRole("status");
    expect(el).toHaveTextContent("3 of 50");
    expect(el).toHaveAttribute("aria-label", "Reviewing label 3 of 50");
  });

  it("clamps current within [1, total]", () => {
    const { getByRole } = renderWithProviders(
      <QueuePosition current={99} total={50} />,
    );
    expect(getByRole("status")).toHaveTextContent("50 of 50");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<QueuePosition current={1} total={1} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
