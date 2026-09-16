import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "./render";

describe("vitest infra", () => {
  it("registers @testing-library/jest-dom matchers", () => {
    const { getByTestId } = renderWithProviders(
      <button type="button" data-testid="b" aria-label="ok">click</button>,
    );
    const el = getByTestId("b");
    expect(el).toBeInTheDocument();
    expect(el).toHaveAccessibleName("ok");
  });

  it("registers vitest-axe and runs against a clean tree", async () => {
    const { container } = renderWithProviders(
      <main>
        <h1>Hello</h1>
        <p>World</p>
      </main>,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
