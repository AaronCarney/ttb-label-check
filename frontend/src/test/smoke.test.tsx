import { describe, it, expect } from "vitest";
import { renderWithProviders } from "./render";

describe("vitest smoke", () => {
  it("renders a div", () => {
    const { container } = renderWithProviders(<div data-testid="x">hello</div>);
    expect(container.querySelector('[data-testid="x"]')).not.toBeNull();
  });
});
