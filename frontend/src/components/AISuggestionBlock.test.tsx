import { describe, it, expect } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { AISuggestionBlock } from "./AISuggestionBlock";
import type { AISuggestionWire } from "../types/envelopes";

const _present: AISuggestionWire = {
  present: true,
  task: "brand_borderline",
  text: "Apostrophe normalization brings extracted brand into agreement.",
  model_disposition: "pass",
};
const _absent: AISuggestionWire = {
  present: false,
  task: null,
  text: null,
  model_disposition: null,
};

describe("AISuggestionBlock", () => {
  it("renders nothing when ai_suggestion.present is false", () => {
    const { container } = renderWithProviders(
      <AISuggestionBlock suggestion={_absent} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders inside <aside> with aria-label='AI suggestion'", () => {
    const { getByRole } = renderWithProviders(
      <AISuggestionBlock suggestion={_present} />,
    );
    expect(getByRole("complementary", { name: /AI suggestion/i })).toBeInTheDocument();
  });

  it("labels itself 'advisory', so it is never read as the verdict", () => {
    const { getByText } = renderWithProviders(
      <AISuggestionBlock suggestion={_present} />,
    );
    expect(getByText(/advisory/i)).toBeInTheDocument();
  });

  it("does NOT render anything resembling a disposition pill at the verdict position", () => {
    const { queryByRole } = renderWithProviders(
      <AISuggestionBlock suggestion={_present} />,
    );
    // An AI suggestion must NEVER be rendered in the verdict's role or position.
    // We assert that it does not expose role=status (DispositionPill's role)
    // anywhere inside the AISuggestionBlock subtree.
    expect(queryByRole("status")).toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <AISuggestionBlock suggestion={_present} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
