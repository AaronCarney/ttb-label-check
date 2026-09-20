/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { CitationPanel } from "./CitationPanel";

const _section = (over: Record<string, unknown> = {}) => ({
  key: "title-27-section-4.33",
  heading: "§ 4.33 Brand names.",
  // The route strips the heading line the file opens with, because the panel
  // prints `heading` itself — see `_body` in `app/cfr/corpus.py`.
  text: "(a) General. The product shall bear a brand name…",
  paragraph: null,
  source_url: "https://www.ecfr.gov/api/versioner/v1/full/2026-09-16/title-27.xml?part=4&section=4.33",
  version_date: "2026-09-16",
  retrieved: "2026-09-20",
  ...over,
});

const _answers = (body: unknown) =>
  vi.fn(async (_input: RequestInfo | URL) => ({ ok: true, json: async () => body }));

beforeEach(() => {
  vi.stubGlobal("fetch", _answers({ citation: "", sections: [] }));
});

describe("CitationPanel", () => {
  // The panel is reserved, not summoned. It is on the page before a reviewer
  // chooses anything, so choosing a citation fills room that was already
  // there rather than covering up what they were reading.
  it("is on the page with nothing chosen, and says what it is for", () => {
    const { getByRole, getByText } = renderWithProviders(<CitationPanel citation={null} />);
    expect(getByRole("region", { name: /regulation/i })).toBeInTheDocument();
    expect(getByText(/choose a citation/i)).toBeInTheDocument();
  });

  it("shows the wording of the section a citation names", async () => {
    vi.stubGlobal("fetch", _answers({ citation: "27 CFR §4.33", sections: [_section()] }));
    const { findByText, getByText } = renderWithProviders(
      <CitationPanel citation="27 CFR §4.33" />,
    );
    expect(await findByText("§ 4.33 Brand names.")).toBeInTheDocument();
    expect(getByText(/The product shall bear a brand name/)).toBeInTheDocument();
  });

  // Provenance is the whole reason this text is allowed to be here: a reviewer
  // has to be able to see which issue of the regulation they are reading.
  it("says which issue of the regulation it is showing, and when it was retrieved", async () => {
    vi.stubGlobal("fetch", _answers({ citation: "27 CFR §4.33", sections: [_section()] }));
    const { findByText } = renderWithProviders(<CitationPanel citation="27 CFR §4.33" />);
    expect(await findByText(/2026-09-16/)).toBeInTheDocument();
    expect(await findByText(/retrieved 2026-09-20/i)).toBeInTheDocument();
  });

  it("names the paragraph the rule rests on, when the citation named one", async () => {
    vi.stubGlobal(
      "fetch",
      _answers({ citation: "27 CFR §4.32(a)(1)", sections: [_section({ paragraph: "(a)(1)" })] }),
    );
    const { findByText } = renderWithProviders(<CitationPanel citation="27 CFR §4.32(a)(1)" />);
    expect(await findByText(/rests on \(a\)\(1\)/i)).toBeInTheDocument();
  });

  it("shows every section a compound citation names", async () => {
    vi.stubGlobal(
      "fetch",
      _answers({
        citation: "27 CFR §4.35(e), 19 CFR §134.45",
        sections: [
          _section({ key: "title-27-section-4.35", heading: "§ 4.35 Name and address." }),
          _section({ key: "title-19-section-134.45", heading: "§ 134.45 Approved markings." }),
        ],
      }),
    );
    const { findByText, getByText } = renderWithProviders(
      <CitationPanel citation="27 CFR §4.35(e), 19 CFR §134.45" />,
    );
    expect(await findByText("§ 4.35 Name and address.")).toBeInTheDocument();
    expect(getByText("§ 134.45 Approved markings.")).toBeInTheDocument();
  });

  // The honest empty state. It must not read as a failure, and it must not
  // read as though the section says nothing.
  it("says the text is not held when the product does not have it", async () => {
    vi.stubGlobal("fetch", _answers({ citation: "27 CFR §9.99", sections: [] }));
    const { findByText } = renderWithProviders(<CitationPanel citation="27 CFR §9.99" />);
    expect(await findByText(/does not hold the text/i)).toBeInTheDocument();
  });

  it("tells a reviewer to try again when the request itself failed", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    const { findByText } = renderWithProviders(<CitationPanel citation="27 CFR §4.33" />);
    expect(await findByText(/could not be loaded/i)).toBeInTheDocument();
  });

  // It fills in place. Announcing it politely is how a reviewer who is not
  // looking at that column finds out it changed.
  it("announces the change politely rather than seizing focus", async () => {
    vi.stubGlobal("fetch", _answers({ citation: "27 CFR §4.33", sections: [_section()] }));
    const { getByRole } = renderWithProviders(<CitationPanel citation="27 CFR §4.33" />);
    const panel = getByRole("region", { name: /regulation/i });
    expect(panel).toHaveAttribute("aria-live", "polite");
    await waitFor(() => expect(document.activeElement).toBe(document.body));
  });

  it("asks the server for the citation exactly as the card prints it", async () => {
    const fetcher = _answers({ citation: "27 CFR §5 Subpart I", sections: [_section()] });
    vi.stubGlobal("fetch", fetcher);
    renderWithProviders(<CitationPanel citation="27 CFR §5 Subpart I" />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const call = fetcher.mock.calls[0];
    expect(call).toBeDefined();
    expect(decodeURIComponent(String(call?.[0]))).toContain("citation=27 CFR §5 Subpart I");
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<CitationPanel citation={null} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
