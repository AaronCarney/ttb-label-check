import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { IncompleteCheckCard } from "./IncompleteCheckCard";

describe("IncompleteCheckCard", () => {
  it("says nothing was checked, and names the code, when no field came back", () => {
    const { getByText } = renderWithProviders(
      <IncompleteCheckCard reasonCode="ENGINE.INPUT.LABEL_IMAGE_MISSING" fieldCount={0} />,
    );
    expect(getByText(/No field on this label was checked/i)).toBeTruthy();
    expect(getByText("ENGINE.INPUT.LABEL_IMAGE_MISSING")).toBeTruthy();
  });

  it("asks for the label to be checked by hand, not submitted again on its own", () => {
    // Submitting the label alone runs the same check on the same photos and
    // shows the reviewer nothing this card does not.
    const { container, getByText } = renderWithProviders(
      <IncompleteCheckCard reasonCode="ENGINE.EXTRACTION.UNAVAILABLE" fieldCount={0} />,
    );
    expect(getByText(/check this label by hand/i)).toBeTruthy();
    expect(container.textContent).not.toMatch(/on its own/i);
  });

  it("warns that a partial result is partial when some fields did come back", () => {
    // The guard now returns what a stopped check had finished. Seven field
    // cards with nothing above them would read as a completed check.
    const { getByText } = renderWithProviders(
      <IncompleteCheckCard reasonCode="ENGINE.SLA.TIMEOUT" fieldCount={7} />,
    );
    expect(getByText(/stopped before it finished/i)).toBeTruthy();
    expect(getByText(/not the same as finding nothing wrong/i)).toBeTruthy();
    expect(getByText("ENGINE.SLA.TIMEOUT")).toBeTruthy();
  });

  it("still says what happened when no code was recorded", () => {
    const { getByText } = renderWithProviders(
      <IncompleteCheckCard reasonCode={null} fieldCount={0} />,
    );
    expect(getByText(/No field on this label was checked/i)).toBeTruthy();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <IncompleteCheckCard reasonCode="ENGINE.SLA.TIMEOUT" fieldCount={7} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
