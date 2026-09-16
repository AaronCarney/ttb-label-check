import { render, type RenderResult } from "@testing-library/react";
import * as React from "react";

export function renderWithProviders(ui: React.ReactElement): RenderResult {
  return render(<React.StrictMode>{ui}</React.StrictMode>);
}
