import { describe, it, expect, vi } from "vitest";
import { fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/render";
import { NeedsBetterPhotoCard } from "./NeedsBetterPhotoCard";

describe("NeedsBetterPhotoCard", () => {
  it("renders reason code and templated applicant message", () => {
    const { getByText } = renderWithProviders(
      <NeedsBetterPhotoCard
        reasonCode="WARNING.LEGIBILITY.LOW_RESOLUTION"
        applicantMessage="Please re-submit a higher-resolution photo (≥300 DPI)."
      />,
    );
    expect(getByText(/WARNING\.LEGIBILITY\.LOW_RESOLUTION/)).toBeInTheDocument();
    expect(getByText(/higher-resolution photo/)).toBeInTheDocument();
  });

  it("renders inside a labelled region (not as an error/alert)", () => {
    const { getByRole, queryByRole } = renderWithProviders(
      <NeedsBetterPhotoCard reasonCode="x" applicantMessage="y" />,
    );
    expect(getByRole("region", { name: /Needs better photo/i })).toBeInTheDocument();
    expect(queryByRole("alert")).toBeNull();
  });

  it("copies the templated message to the clipboard via Copy button", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(global.navigator, "clipboard", {
      value: { writeText },
      writable: true,
      configurable: true,
    });
    const { getByRole } = renderWithProviders(
      <NeedsBetterPhotoCard reasonCode="x" applicantMessage="HELLO" />,
    );
    fireEvent.click(getByRole("button", { name: /Copy message/i }));
    // Allow async handler to settle
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith("HELLO"));
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <NeedsBetterPhotoCard reasonCode="x" applicantMessage="y" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
